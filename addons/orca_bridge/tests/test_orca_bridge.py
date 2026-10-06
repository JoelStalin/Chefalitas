import importlib.util
import json
from unittest.mock import patch

import requests

from odoo.exceptions import AccessError
from odoo.modules.module import get_module_path
from odoo.tests import HttpCase, TransactionCase, tagged

from odoo.addons.orca_bridge.models.orca_bridge_client import EVENTS_KEY, post_events

SETTINGS = {
    "orca_bridge.url": "https://orca.test",
    "orca_bridge.token": "orca-token-for-tests",
    "orca_bridge.connection_id": "chefalitas-test",
}


def _configure(env, push=True):
    params = env["ir.config_parameter"].sudo()
    for key, value in SETTINGS.items():
        params.set_str(key, value)
    params.set_bool("orca_bridge.push_events", push)


@tagged("post_install", "-at_install")
class TestOrcaBridgeUser(TransactionCase):

    def test_orca_user_is_internal_without_password(self):
        user = self.env.ref("orca_bridge.user_orca_bridge")
        self.assertTrue(user._is_internal())
        self.assertTrue(user.has_group("account.group_account_invoice"))
        self.assertTrue(user.has_group("point_of_sale.group_pos_user"))
        self.assertFalse(user.has_group("base.group_system"))
        self.env.cr.execute("SELECT password FROM res_users WHERE id = %s", (user.id,))
        self.assertFalse(self.env.cr.fetchone()[0])

    def test_generate_api_key_rotates_and_authenticates(self):
        settings = self.env["res.config.settings"].create({})
        user = self.env.ref("orca_bridge.user_orca_bridge")
        Keys = self.env["res.users.apikeys"].sudo()
        first = settings.action_orca_bridge_generate_api_key()["context"]["default_key"]
        self.assertEqual(Keys._check_credentials(scope="rpc", key=first), user.id)
        second = settings.action_orca_bridge_generate_api_key()["context"]["default_key"]
        self.assertNotEqual(first, second)
        self.assertFalse(Keys._check_credentials(scope="rpc", key=first), "previous key must be revoked")
        self.assertEqual(Keys._check_credentials(scope="rpc", key=second), user.id)
        settings.invalidate_recordset(["orca_bridge_api_key_count"])
        self.assertEqual(settings.orca_bridge_api_key_count, 1)
        settings.action_orca_bridge_revoke_api_keys()
        self.assertFalse(Keys._check_credentials(scope="rpc", key=second))

    def test_only_admins_generate_keys(self):
        accountant = self.env["res.users"].create({
            "name": "Contador", "login": "contador_orca_test",
            "group_ids": [(6, 0, [self.env.ref("account.group_account_manager").id,
                                  self.env.ref("base.group_user").id])],
        })
        settings = self.env["res.config.settings"].create({})
        with self.assertRaises(AccessError):
            settings.with_user(accountant).action_orca_bridge_generate_api_key()


@tagged("post_install", "-at_install")
class TestOrcaBridgeEvents(TransactionCase):

    def _pending(self):
        return self.env.cr.postcommit.data.get(EVENTS_KEY) or {}

    def test_no_events_when_disabled(self):
        _configure(self.env, push=False)
        self.env["res.partner"].create({"name": "Sin ORCA"})
        self.assertFalse(self._pending())

    def test_events_are_aggregated_ids_and_field_names_only(self):
        _configure(self.env)
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
        with patch("odoo.addons.orca_bridge.models.orca_bridge_client.requests.post") as post:
            post.return_value.status_code = 202
            post_events("https://orca.test", "tok", events)
        post.assert_called_once()
        self.assertEqual(post.call_args.args[0], "https://orca.test/api/orca/odoo-bridge/events")
        self.assertEqual(post.call_args.kwargs["headers"], {"Authorization": "Bearer tok"})
        self.assertEqual(post.call_args.kwargs["json"], events[0])
        with patch("odoo.addons.orca_bridge.models.orca_bridge_client.requests.post",
                   side_effect=requests.ConnectionError("down")):
            post_events("https://orca.test", "tok", events)  # logged, not raised

    def test_test_connection_reports_scopes(self):
        _configure(self.env)
        settings = self.env["res.config.settings"].create({})
        with patch("odoo.addons.orca_bridge.models.orca_bridge_client.requests.request") as req:
            req.return_value.status_code = 200
            req.return_value.json.return_value = {"client": "odoo-test", "scopes": ["events"], "connections": ["chefalitas-test"]}
            action = settings.action_orca_bridge_test_connection()
        self.assertEqual(action["params"]["type"], "success")
        self.assertEqual(req.call_args.args[:2], ("GET", "https://orca.test/api/orca/odoo-bridge/whoami"))


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
class TestOrcaBridgeJson2(HttpCase):
    """What ORCA does: call Odoo's JSON-2 API with the ORCA user's key."""

    def _json2(self, key, model, method, payload):
        return self.url_open(
            f"/json/2/{model}/{method}", data=json.dumps(payload),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                     "X-Odoo-Database": self.env.cr.dbname},
        )

    def test_orca_key_reads_and_writes_within_user_rights(self):
        settings = self.env["res.config.settings"].create({})
        key = settings.action_orca_bridge_generate_api_key()["context"]["default_key"]
        created = self._json2(key, "res.partner", "create", {"vals_list": [{"name": "Desde ORCA"}]})
        self.assertEqual(created.status_code, 200, created.text)
        partner_id = created.json()[0]
        rows = self._json2(key, "res.partner", "read", {"ids": [partner_id], "fields": ["name", "create_uid"]}).json()
        self.assertEqual(rows[0]["name"], "Desde ORCA")
        self.assertEqual(rows[0]["create_uid"][0], self.env.ref("orca_bridge.user_orca_bridge").id)
        denied = self._json2(key, "res.users", "create", {"vals_list": [{"name": "x", "login": "x_orca"}]})
        self.assertEqual(denied.status_code, 403, denied.text)
        self.assertEqual(self._json2("wrong-key", "res.partner", "search_count", {"domain": []}).status_code, 401)
