import base64
import hashlib
import logging
import secrets
import threading
import time
from urllib.parse import urlencode

import requests

from odoo import api, models, release
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

EVENTS_KEY = "orca_bridge.events"
TIMEOUT = 10
MAX_IDS = 200
CALLBACK_PATH = "/orca_bridge/oauth/callback"
API_KEY_SCOPE = "rpc"  # Odoo 20 JSON-2 API (/json/2/<model>/<method>)
API_KEY_NAME = "ORCA bridge"
P = "orca_bridge."  # ir.config_parameter prefix
SECRET_PARAMS = ("client_secret", "access_token", "refresh_token")


def post_events(url, token, events):
    """Send change events to ORCA. Runs after commit in a background thread: never raises."""
    for event in events:
        try:
            response = requests.post(
                f"{url}/api/orca/odoo-bridge/events",
                json=event,
                headers={"Authorization": f"Bearer {token}"},
                timeout=TIMEOUT,
            )
        except requests.RequestException as exc:
            _logger.warning("orca_bridge: ORCA not reachable (%s); event %s/%s dropped",
                            exc, event["model"], event["event"])
            continue
        if response.status_code >= 300:
            _logger.warning("orca_bridge: ORCA refused event %s/%s: HTTP %s",
                            event["model"], event["event"], response.status_code)


class OrcaBridgeClient(models.AbstractModel):
    """Odoo -> ORCA: OAuth 2.0 connector (authorization code + PKCE), requests and change events."""

    _name = "orca.bridge.client"
    _description = "ORCA bridge client"

    # ------------------------------------------------------------------ settings

    @api.model
    def _params(self):
        return self.env["ir.config_parameter"].sudo()

    @api.model
    def _settings(self):
        params = self._params()
        return {
            "url": (params.get_str(P + "url") or "").rstrip("/"),
            "client_id": params.get_str(P + "client_id") or "",
            "client_secret": params.get_str(P + "client_secret") or "",
            "connection": params.get_str(P + "connection_id") or "",
            "company": params.get_str(P + "company") or "",
            "connected_at": params.get_str(P + "connected_at") or "",
            "push_events": params.get_bool(P + "push_events"),
        }

    @api.model
    def _base_url(self):
        return (self._params().get_str("web.base.url") or "").rstrip("/")

    @api.model
    def _redirect_uri(self):
        return self._base_url() + CALLBACK_PATH

    @api.model
    def _is_connected(self):
        return bool(self._params().get_str(P + "refresh_token") and self._settings()["connection"])

    # ------------------------------------------------------------------ OAuth 2.0

    @api.model
    def _authorize_url(self):
        """Start of the flow: returns (url, pending) where pending must be kept in the user's session."""
        s = self._settings()
        if not (s["url"] and s["client_id"] and s["client_secret"]):
            raise UserError(self.env._("Configure la URL de ORCA, el Client ID y el Client secret (ORCA > Configuracion)."))
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        state = secrets.token_urlsafe(24)
        query = urlencode({
            "response_type": "code",
            "client_id": s["client_id"],
            "redirect_uri": self._redirect_uri(),
            "scope": "odoo.connect events",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        })
        return f"{s['url']}/oauth/authorize?{query}", {"state": state, "verifier": verifier, "ts": time.time()}

    @api.model
    def _token_request(self, data):
        s = self._settings()
        try:
            response = requests.post(f"{s['url']}/oauth/token", timeout=TIMEOUT, data={
                **data, "client_id": s["client_id"], "client_secret": s["client_secret"]})
        except requests.RequestException as exc:
            raise UserError(self.env._("ORCA no responde: %s", exc)) from exc
        body = self._json(response)
        if response.status_code != 200:
            raise UserError(self.env._("ORCA rechazo la autorizacion: %s",
                                       body.get("error_description") or body.get("error") or response.status_code))
        self._store_tokens(body)
        return body

    @api.model
    def _store_tokens(self, body):
        params = self._params()
        params.set_str(P + "access_token", body["access_token"])
        params.set_str(P + "refresh_token", body["refresh_token"])
        params.set_int(P + "token_expires_at", int(time.time()) + int(body.get("expires_in", 3600)) - 60)

    @api.model
    def _access_token(self):
        params = self._params()
        token = params.get_str(P + "access_token")
        if token and params.get_int(P + "token_expires_at") > time.time():
            return token
        refresh = params.get_str(P + "refresh_token")
        if not refresh:
            raise UserError(self.env._("Odoo no esta conectado a ORCA: use 'Conectar con ORCA' en Ajustes."))
        return self._token_request({"grant_type": "refresh_token", "refresh_token": refresh})["access_token"]

    @api.model
    def _complete_oauth(self, code, verifier):
        """Callback: exchange the code, hand ORCA the ORCA user's API key and register this database."""
        tokens = self._token_request({
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": self._redirect_uri(), "code_verifier": verifier,
        })
        # ORCA verifies the key by calling Odoo back during the registration: the key must already be
        # committed, so it is issued (and revoked on failure) in its own transaction.
        api_key = self._rotate_api_key(issue=True)
        try:
            result = self._request("POST", "/api/orca/odoo-bridge/connections/register", {
                "url": self._base_url(), "db": self.env.cr.dbname, "api_key": api_key,
                "odoo_version": release.version,
            })
        except Exception:
            self._rotate_api_key(issue=False)
            raise
        params = self._params()
        company = (tokens.get("company") or {}).get("name") or result.get("company") or ""
        params.set_str(P + "connection_id", result["connection_id"])
        params.set_str(P + "company", company)
        params.set_str(P + "connected_at", time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()))
        return {**result, "company": company}

    @api.model
    def _rotate_api_key(self, issue):
        """Revoke the ORCA user's JSON-2 keys and, if issue, create a new one; committed on its own cursor."""
        with self.env.registry.cursor() as cr:
            env = self.env(cr=cr)
            user = env.ref("orca_bridge.user_orca_bridge")
            keys = env["res.users.apikeys"].with_user(user).sudo()
            keys.search([("user_id", "=", user.id), ("scope", "=", API_KEY_SCOPE)]).unlink()
            return keys._generate(API_KEY_SCOPE, API_KEY_NAME, None) if issue else None

    @api.model
    def _disconnect(self):
        params = self._params()
        s = self._settings()
        try:
            if self._is_connected():
                self._request("POST", "/api/orca/odoo-bridge/connections/unregister", {"db": self.env.cr.dbname})
                requests.post(f"{s['url']}/oauth/revoke", timeout=TIMEOUT,
                              data={"token": params.get_str(P + "refresh_token")})
        except (UserError, requests.RequestException) as exc:
            _logger.warning("orca_bridge: ORCA could not be notified of the disconnection: %s", exc)
        self._rotate_api_key(issue=False)
        for key in ("access_token", "refresh_token", "token_expires_at", "connection_id", "company", "connected_at"):
            params.search([("key", "=", P + key)]).unlink()

    # ------------------------------------------------------------------ requests

    @staticmethod
    def _json(response):
        try:
            return response.json() or {}
        except ValueError:
            return {}

    @api.model
    def _request(self, method, path, payload=None):
        s = self._settings()
        if not s["url"]:
            raise UserError(self.env._("Configure la URL de ORCA en Ajustes > ORCA."))
        try:
            response = requests.request(
                method, s["url"] + path, json=payload, timeout=TIMEOUT,
                headers={"Authorization": f"Bearer {self._access_token()}"},
            )
        except requests.RequestException as exc:
            raise UserError(self.env._("ORCA no responde: %s", exc)) from exc
        body = self._json(response)
        if response.status_code >= 300:
            error = body.get("error") or {}
            message = error.get("message") if isinstance(error, dict) else body.get("error_description") or error
            raise UserError(self.env._(
                "ORCA respondio %(status)s: %(message)s",
                status=response.status_code, message=message or response.text[:200],
            ))
        return body

    # ------------------------------------------------------------------ change events

    @api.model
    def _push_event(self, records, event, fields=()):
        """Queue a change notification; it is sent only if the transaction commits."""
        if not records.ids:
            return
        settings = self._settings()
        if not (settings["push_events"] and settings["url"] and settings["connection"]):
            return
        postcommit = self.env.cr.postcommit
        pending = postcommit.data.get(EVENTS_KEY)
        if pending is None:
            pending = postcommit.data[EVENTS_KEY] = {}
            postcommit.add(self._flush_callback(settings, pending))
        entry = pending.setdefault((records._name, event), {"ids": set(), "fields": set()})
        entry["ids"].update(records.ids)
        entry["fields"].update(fields)

    @api.model
    def _events_payload(self, connection, pending):
        events = []
        for (model, event), entry in sorted(pending.items()):
            ids = sorted(entry["ids"])
            for start in range(0, len(ids), MAX_IDS):
                events.append({
                    "connection": connection,
                    "model": model,
                    "event": event,
                    "ids": ids[start:start + MAX_IDS],
                    "fields": sorted(entry["fields"])[:200],
                })
        return events

    @api.model
    def _flush_callback(self, settings, pending):
        def flush():
            events = self._events_payload(settings["connection"], pending)
            if not events:
                return
            try:
                # token refresh needs the database: done here, after commit, in a fresh cursor
                with self.env.registry.cursor() as cr:
                    token = self.with_env(self.env(cr=cr))._access_token()
            except Exception as exc:  # noqa: BLE001 - never break the user's transaction aftermath
                _logger.warning("orca_bridge: no ORCA access token (%s); %s event(s) dropped", exc, len(events))
                return
            threading.Thread(
                target=post_events, args=(settings["url"], token, events),
                name="orca-bridge-events", daemon=True,
            ).start()
        return flush
