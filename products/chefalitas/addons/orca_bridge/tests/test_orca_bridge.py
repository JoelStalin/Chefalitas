import base64
import hashlib
import importlib.util
import json
import time
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import requests

from odoo.exceptions import AccessError, UserError
from odoo.modules.module import get_module_path
from odoo.tests import HttpCase, TransactionCase, tagged

from odoo.addons.orca_bridge.models.orca_bridge_client import EVENTS_KEY, post_events

CLIENT = "odoo.addons.orca_bridge.models.orca_bridge_client.requests"
ORCA = "https://orca.test"


def _response(status, body):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body
    r.text = json.dumps(body)
    return r


def _configure(env, push=True):
    params = env["ir.config_parameter"].sudo()
    params.set_str("orca_bridge.url", ORCA)
    params.set_str("orca_bridge.client_id", "orca_cli_test")
    params.set_str("orca_bridge.client_secret", "orca_cs_secret")
    params.set_bool("orca_bridge.push_events", push)


TOKENS = {"access_token": "orca_at_1", "refresh_token": "orca_rt_1", "expires_in": 3600, "token_type": "Bearer",
          "scope": "odoo.connect events", "company": {"id": "c1", "name": "Chefalitas", "slug": "chefalitas"}}


class OrcaFake:
    """Records the calls Odoo makes to ORCA (token endpoint, register, unregister, revoke)."""

    def __init__(self, register_status=200):
        self.posts = []
        self.requests = []
        self.register_status = register_status

    def post(self, url, data=None, json=None, headers=None, timeout=None):
        self.posts.append((url, data))
        if url.endswith("/oauth/token"):
            if data.get("grant_type") == "refresh_token":
                return _response(200, {**TOKENS, "access_token": "orca_at_2", "refresh_token": "orca_rt_2"})
            return _response(200, TOKENS)
        return _response(200, {})

    def request(self, method, url, json=None, headers=None, timeout=None):
        self.requests.append((method, url, json, headers))
        if url.endswith("/connections/register"):
            if self.register_status != 200:
                return _response(self.register_status, {"error": {"code": "invalid_request", "message": "boom"}})
            return _response(200, {"connection_id": "chefalitas-" + json["db"], "company": "chefalitas", "reachable": True})
        if url.endswith("/whoami"):
            return _response(200, {"client": "oauth:Odoo", "scopes": ["odoo.connect", "events"], "company": "chefalitas"})
        return _response(200, {"disconnected": True})

    def patch(self):
        fake = self
        mod = MagicMock(wraps=requests)
        mod.post.side_effect = fake.post
        mod.request.side_effect = fake.request
        mod.RequestException = requests.RequestException
        return patch(CLIENT, mod)


@tagged("post_install", "-at_install")
class TestOrcaConnector(TransactionCase):

    def setUp(self):
        super().setUp()
        # the API key is issued on its own cursor (committed before ORCA calls back): keep it in the test transaction
        self.enterContext(self.registry_test_mode())
        _configure(self.env)
        self.client = self.env["orca.bridge.client"]
        self.Keys = self.env["res.users.apikeys"].sudo()
        self.orca_user = self.env.ref("orca_bridge.user_orca_bridge")

    def test_orca_user_is_administrator_without_password(self):
        self.assertTrue(self.orca_user._is_internal())
        self.assertTrue(self.orca_user.has_group("base.group_system"))
        self.assertTrue(self.orca_user.has_group("account.group_account_manager"))
        self.env.cr.execute("SELECT password FROM res_users WHERE id = %s", (self.orca_user.id,))
        self.assertFalse(self.env.cr.fetchone()[0])

    def test_authorize_url_uses_pkce_s256(self):
        url, pending = self.client._authorize_url()
        q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
        self.assertTrue(url.startswith(ORCA + "/oauth/authorize?"))
        self.assertEqual(q["client_id"], "orca_cli_test")
        self.assertEqual(q["redirect_uri"], self.client._base_url() + "/orca_bridge/oauth/callback")
        self.assertEqual(q["code_challenge_method"], "S256")
        expected = base64.urlsafe_b64encode(hashlib.sha256(pending["verifier"].encode()).digest()).rstrip(b"=").decode()
        self.assertEqual(q["code_challenge"], expected)
        self.assertEqual(q["state"], pending["state"])
        self.assertNotIn("client_secret", url)

    def test_authorize_needs_configuration(self):
        self.env["ir.config_parameter"].sudo().set_str("orca_bridge.client_secret", "")
        with self.assertRaises(UserError):
            self.client._authorize_url()

    def test_complete_oauth_registers_database_with_fresh_api_key(self):
        fake = OrcaFake()
        with fake.patch():
            result = self.client._complete_oauth("the-code", "the-verifier")
        token_call = fake.posts[0][1]
        self.assertEqual(token_call["grant_type"], "authorization_code")
        self.assertEqual(token_call["code_verifier"], "the-verifier")
        method, url, payload, headers = fake.requests[0]
        self.assertEqual(url, ORCA + "/api/orca/odoo-bridge/connections/register")
        self.assertEqual(headers["Authorization"], "Bearer orca_at_1")
        self.assertEqual(payload["db"], self.env.cr.dbname)
        self.assertEqual(self.Keys._check_credentials(scope="rpc", key=payload["api_key"]), self.orca_user.id)
        self.assertEqual(result["connection_id"], "chefalitas-" + self.env.cr.dbname)
        self.assertTrue(self.client._is_connected())
        s = self.client._settings()
        self.assertEqual((s["company"], s["connection"]), ("Chefalitas", "chefalitas-" + self.env.cr.dbname))

    def test_failed_registration_revokes_the_new_key(self):
        fake = OrcaFake(register_status=400)
        with fake.patch(), self.assertRaises(UserError):
            self.client._complete_oauth("the-code", "the-verifier")
        key = fake.requests[0][2]["api_key"]
        self.assertFalse(self.Keys._check_credentials(scope="rpc", key=key))

    def test_expired_access_token_is_refreshed(self):
        fake = OrcaFake()
        with fake.patch():
            self.client._complete_oauth("c", "v")
            self.env["ir.config_parameter"].sudo().set_int("orca_bridge.token_expires_at", int(time.time()) - 10)
            self.assertEqual(self.client._access_token(), "orca_at_2")
        self.assertEqual(fake.posts[-1][1]["grant_type"], "refresh_token")
        self.assertEqual(fake.posts[-1][1]["refresh_token"], "orca_rt_1")

    def test_disconnect_revokes_everything(self):
        fake = OrcaFake()
        with fake.patch():
            self.client._complete_oauth("c", "v")
            key = fake.requests[0][2]["api_key"]
            self.client._disconnect()
        self.assertFalse(self.client._is_connected())
        self.assertFalse(self.Keys._check_credentials(scope="rpc", key=key))
        self.assertIn(ORCA + "/api/orca/odoo-bridge/connections/unregister", [r[1] for r in fake.requests])
        self.assertIn(ORCA + "/oauth/revoke", [p[0] for p in fake.posts])

    def test_settings_buttons_are_admin_only(self):
        accountant = self.env["res.users"].create({
            "name": "Contador", "login": "contador_orca_test",
            "group_ids": [(6, 0, [self.env.ref("account.group_account_manager").id, self.env.ref("base.group_user").id])],
        })
        settings = self.env["res.config.settings"].create({})
        for action in ("action_orca_bridge_connect", "action_orca_bridge_disconnect", "action_orca_bridge_test_connection"):
            with self.assertRaises(AccessError):
                getattr(settings.with_user(accountant), action)()
        self.assertEqual(settings.action_orca_bridge_connect()["url"], "/orca_bridge/oauth/start")

    def test_test_connection_uses_oauth_token(self):
        fake = OrcaFake()
        with fake.patch():
            self.client._complete_oauth("c", "v")
            action = self.env["res.config.settings"].create({}).action_orca_bridge_test_connection()
        self.assertEqual(action["params"]["type"], "success")
        self.assertEqual(fake.requests[-1][3]["Authorization"], "Bearer orca_at_1")


@tagged("post_install", "-at_install")
class TestOrcaBridgeEvents(TransactionCase):

    def _pending(self):
        return self.env.cr.postcommit.data.get(EVENTS_KEY) or {}

    def _connect(self, push=True):
        _configure(self.env, push=push)
        self.env["ir.config_parameter"].sudo().set_str("orca_bridge.connection_id", "chefalitas-test")

    def test_no_events_when_disabled_or_not_connected(self):
        self._connect(push=False)
        self.env["res.partner"].create({"name": "Sin ORCA"})
        self.assertFalse(self._pending())
        _configure(self.env, push=True)
        self.env["ir.config_parameter"].sudo().set_str("orca_bridge.connection_id", "")
        self.env["res.partner"].create({"name": "Sin conexion"})
        self.assertFalse(self._pending())

    def test_events_are_aggregated_ids_and_field_names_only(self):
        self._connect()
        partners = self.env["res.partner"].create([{"name": "A", "vat": "131793916"}, {"name": "B"}])
        partners[0].write({"email": "a@example.test"})
        pending = self._pending()
        self.assertEqual(pending[("res.partner", "create")]["ids"], set(partners.ids))
        self.assertLessEqual({"name", "vat"}, pending[("res.partner", "create")]["fields"])
        self.assertEqual(pending[("res.partner", "write")]["fields"], {"email"})
        payload = self.env["orca.bridge.client"]._events_payload("chefalitas-test", pending)
        self.assertIn({"connection": "chefalitas-test", "model": "res.partner", "event": "write",
                       "ids": [partners[0].id], "fields": ["email"]}, payload)
        self.assertNotIn("a@example.test", json.dumps(payload))

    def test_payload_chunks_large_id_sets(self):
        pending = {("pos.order", "write"): {"ids": set(range(1, 451)), "fields": {"state"}}}
        payload = self.env["orca.bridge.client"]._events_payload("c", pending)
        self.assertEqual([len(e["ids"]) for e in payload], [200, 200, 50])

    def test_post_events_sends_bearer_and_never_raises(self):
        events = [{"connection": "c", "model": "res.partner", "event": "create", "ids": [1], "fields": []}]
        with patch(CLIENT + ".post") as post:
            post.return_value.status_code = 202
            post_events(ORCA, "tok", events)
        self.assertEqual(post.call_args.args[0], ORCA + "/api/orca/odoo-bridge/events")
        self.assertEqual(post.call_args.kwargs["headers"], {"Authorization": "Bearer tok"})
        with patch(CLIENT + ".post", side_effect=requests.ConnectionError("down")):
            post_events(ORCA, "tok", events)  # logged, not raised


@tagged("post_install", "-at_install")
class TestOrcaBridgeMigration(TransactionCase):

    def test_migration_removes_old_shared_token(self):
        self.env["ir.config_parameter"].sudo().set_str("orca.api_token", "old-shared-token")
        path = get_module_path("orca_bridge") + "/migrations/20.0.2.0.0/post-migrate.py"
        spec = importlib.util.spec_from_file_location("orca_bridge_post_migrate_20_2", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.migrate(self.env.cr, "20.0.1.0.0")
        self.env.cr.execute("SELECT 1 FROM ir_config_parameter WHERE key = %s", ("orca.api_token",))
        self.assertFalse(self.env.cr.fetchall())


@tagged("post_install", "-at_install")
class TestOrcaOAuthHttp(HttpCase):
    """Browser side of the connector, plus what ORCA then does: JSON-2 calls with the handed-over key."""

    def setUp(self):
        super().setUp()
        _configure(self.env)
        self.authenticate("admin", "admin")

    def test_full_connect_flow_and_json2_access(self):
        start = self.url_open("/orca_bridge/oauth/start", allow_redirects=False)
        self.assertIn(start.status_code, (302, 303))
        location = start.headers["Location"]
        self.assertTrue(location.startswith(ORCA + "/oauth/authorize?"))
        state = parse_qs(urlparse(location).query)["state"][0]

        bad = self.url_open("/orca_bridge/oauth/callback?code=x&state=forged")
        self.assertIn("vencida o no valida", bad.text)

        # a forged state consumed the pending request: start again
        start = self.url_open("/orca_bridge/oauth/start", allow_redirects=False)
        state = parse_qs(urlparse(start.headers["Location"]).query)["state"][0]
        fake = OrcaFake()
        with fake.patch():
            done = self.url_open(f"/orca_bridge/oauth/callback?code=good&state={state}")
        self.assertIn("conectado a ORCA (Chefalitas)", done.text)
        key = fake.requests[0][2]["api_key"]
        self.logout()  # ORCA calls without the admin's browser session

        def json2(model, method, payload, api_key=key):
            return self.url_open(f"/json/2/{model}/{method}", data=json.dumps(payload), headers={
                "Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                "X-Odoo-Database": self.env.cr.dbname})

        created = json2("res.partner", "create", {"vals_list": [{"name": "Desde ORCA"}]})
        self.assertEqual(created.status_code, 200, created.text)
        # ORCA controls the environment: settings-level models are reachable too
        users = json2("res.users", "search_count", {"domain": []})
        self.assertEqual(users.status_code, 200, users.text)
        self.assertEqual(json2("res.partner", "search_count", {"domain": []}, api_key="wrong").status_code, 401)

    def test_denied_consent_shows_message(self):
        start = self.url_open("/orca_bridge/oauth/start", allow_redirects=False)
        state = parse_qs(urlparse(start.headers["Location"]).query)["state"][0]
        res = self.url_open(f"/orca_bridge/oauth/callback?error=access_denied&error_description=El+usuario+cancelo&state={state}")
        self.assertIn("El usuario cancelo", res.text)
