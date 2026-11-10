"""WhatsApp account with two providers (GetUpSoft code, from public documentation):

- qr (default, decision of the user 2026-10-08): a WhatsApp Web session in the GetUpSoft gateway
  (platform/wa-gateway in ORCA), linked by scanning a QR. Outside WhatsApp's terms: the number can be banned.
- cloud: Meta WhatsApp Cloud API, configured by hand (token, number id, app secret) or linked through Meta's
  OAuth consent screen (Embedded Signup configuration).
Every account has its own secrets and its own gateway session: companies never share one.
"""
import base64
import hashlib
import hmac
import logging
import secrets
from urllib.parse import urlencode

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.binary import BinaryBytes

_logger = logging.getLogger(__name__)

GRAPH_VERSION = "v21.0"
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"
TIMEOUT = 20


class GsWhatsappAccount(models.Model):
    _name = "gs.whatsapp.account"
    _description = "WhatsApp account"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    provider = fields.Selection([("qr", "QR (WhatsApp Web, gateway GetUpSoft)"), ("cloud", "Meta Cloud API (oficial)")],
                                required=True, default="qr")
    display_number = fields.Char("Number shown to customers")
    state = fields.Selection([("draft", "Sin vincular"), ("qr", "Esperando escaneo"), ("connected", "Conectada"),
                              ("error", "Error")], default="draft", readonly=True)
    last_error = fields.Char(readonly=True)

    # QR gateway
    gateway_url = fields.Char("Gateway URL", default="http://127.0.0.1:18830")
    gateway_token = fields.Char("Gateway token", groups="base.group_system", copy=False)
    gateway_session = fields.Char("Gateway session", readonly=True, copy=False)
    gateway_secret = fields.Char(groups="base.group_system", copy=False, default=lambda self: secrets.token_urlsafe(32))
    qr_image = fields.Binary("QR", readonly=True, attachment=False)

    # Meta Cloud API
    phone_number_id = fields.Char("Phone number ID", help="Meta: WhatsApp > API setup > Phone number ID")
    waba_id = fields.Char("WhatsApp Business Account ID")
    token = fields.Char("Access token", groups="base.group_system", copy=False)
    app_secret = fields.Char("App secret", groups="base.group_system", copy=False,
                             help="Checks the X-Hub-Signature-256 of every Meta webhook call")
    verify_token = fields.Char("Webhook verify token", copy=False, groups="base.group_system",
                               default=lambda self: secrets.token_urlsafe(24))
    meta_app_id = fields.Char("Meta App ID", help="For 'Vincular con Meta' (OAuth consent screen)")
    meta_config_id = fields.Char("Embedded Signup configuration ID")
    oauth_state = fields.Char(copy=False, groups="base.group_system")
    webhook_url = fields.Char(compute="_compute_webhook_url")

    @api.constrains("provider", "phone_number_id", "gateway_url")
    def _check_provider(self):
        for account in self:
            if account.provider == "qr" and not account.gateway_url:
                raise ValidationError(_("The QR provider needs the gateway URL."))

    def _base_url(self):
        return (self.env["ir.config_parameter"].sudo().get_str("web.base.url") or "").rstrip("/")

    def _compute_webhook_url(self):
        for account in self:
            path = "qr_webhook" if account.provider == "qr" else "webhook"
            account.webhook_url = f"{account._base_url()}/getupsoft_whatsapp/{path}"

    # ================================================================== QR provider (gateway)
    def _gateway(self, method, path, payload=None):
        self.ensure_one()
        try:
            r = requests.request(method, f"{self.gateway_url.rstrip('/')}{path}", json=payload, timeout=40,
                                 headers={"Authorization": f"Bearer {self.sudo().gateway_token or ''}"})
        except requests.RequestException as exc:
            raise UserError(_("The WhatsApp gateway is not reachable: %s", exc)) from exc
        if r.status_code >= 300:
            raise UserError(_("The WhatsApp gateway answered %(status)s: %(detail)s", status=r.status_code, detail=r.text[:200]))
        return r.json()

    def _session_id(self):
        return self.gateway_session or f"odoo-{self.env.cr.dbname}-{self.id}".lower().replace("_", "-")[:60]

    def _apply_gateway_state(self, data):
        qr = data.get("qr") or ""
        image = base64.b64decode(qr.split(",", 1)[1]) if qr.startswith("data:image") else None
        self.write({
            "gateway_session": data.get("id") or self.gateway_session,
            "state": {"open": "connected", "qr": "qr"}.get(data.get("status"), "draft"),
            "qr_image": BinaryBytes(image, "qr.png") if image else False,  # Odoo 20 binary value
            "display_number": f"+{data['me']}" if data.get("me") else self.display_number,
            "last_error": False,
        })

    def action_qr_link(self):
        """Start (or resume) the gateway session and show the QR to scan from WhatsApp > Linked devices."""
        self.ensure_one()
        session = self._session_id()
        data = self._gateway("POST", f"/sessions/{session}", {
            "webhook_url": f"{self._base_url()}/getupsoft_whatsapp/qr_webhook",
            "webhook_secret": self.sudo().gateway_secret})
        self._apply_gateway_state(data)
        return True

    def action_qr_refresh(self):
        self.ensure_one()
        self._apply_gateway_state(self._gateway("GET", f"/sessions/{self._session_id()}"))
        return True

    def action_qr_logout(self):
        self.ensure_one()
        self._gateway("DELETE", f"/sessions/{self._session_id()}")
        self.write({"state": "draft", "qr_image": False, "gateway_session": False})
        return True

    def _qr_signature_ok(self, body: bytes, header: str) -> bool:
        self.ensure_one()
        if not header or not header.startswith("sha256="):
            return False
        expected = hmac.new(self.sudo().gateway_secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, header[7:])

    # ================================================================== Meta Cloud API provider
    @api.model
    def _by_verify_token(self, token):
        return self.sudo().search([("verify_token", "=", token)], limit=1) if token else self.browse()

    def _signature_ok(self, body: bytes, header: str) -> bool:
        """Meta signs the raw body with the app secret: X-Hub-Signature-256: sha256=<hex>."""
        self.ensure_one()
        if not header or not header.startswith("sha256=") or not self.sudo().app_secret:
            return False
        expected = hmac.new(self.sudo().app_secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, header[7:])

    def _graph(self, method, path, token=None, **kwargs):
        self.ensure_one()
        try:
            response = requests.request(method, f"{GRAPH}/{path}", timeout=TIMEOUT,
                                        headers={"Authorization": f"Bearer {token or self.sudo().token}"}, **kwargs)
        except requests.RequestException as exc:
            raise UserError(_("WhatsApp is not reachable: %s", exc)) from exc
        if response.status_code >= 300:
            try:
                detail = response.json().get("error", {}).get("message")
            except ValueError:
                detail = response.text[:200]
            raise UserError(_("WhatsApp refused the request (HTTP %(status)s): %(detail)s",
                              status=response.status_code, detail=detail))
        return response

    def _download_media(self, media_id):
        """Media id -> (bytes, mimetype). Meta returns a short-lived URL that needs the same token."""
        meta = self._graph("GET", media_id).json()
        data = requests.get(meta["url"], headers={"Authorization": f"Bearer {self.sudo().token}"}, timeout=TIMEOUT)
        if data.status_code >= 300:
            raise UserError(_("Could not download the WhatsApp media (HTTP %s)", data.status_code))
        return data.content, meta.get("mime_type") or data.headers.get("Content-Type", "application/octet-stream")

    def _meta_redirect_uri(self):
        return f"{self._base_url()}/getupsoft_whatsapp/meta/callback"

    def action_meta_connect(self):
        """Quick link: Meta's OAuth consent screen (Embedded Signup configuration) -> token, WABA and number."""
        self.ensure_one()
        if not (self.meta_app_id and self.meta_config_id and self.sudo().app_secret):
            raise UserError(_("Fill in Meta App ID, Embedded Signup configuration ID and App secret first."))
        state = f"{self.id}:{secrets.token_urlsafe(24)}"
        self.sudo().oauth_state = state
        url = f"https://www.facebook.com/{GRAPH_VERSION}/dialog/oauth?" + urlencode({
            "client_id": self.meta_app_id, "config_id": self.meta_config_id, "redirect_uri": self._meta_redirect_uri(),
            "response_type": "code", "override_default_response_type": "true", "state": state})
        return {"type": "ir.actions.act_url", "url": url, "target": "self"}

    def _meta_complete(self, code):
        """OAuth callback: code -> long-lived token; the granted WABA and its first number are stored."""
        self.ensure_one()
        sudo = self.sudo()
        token = requests.get(f"{GRAPH}/oauth/access_token", timeout=TIMEOUT, params={
            "client_id": self.meta_app_id, "client_secret": sudo.app_secret,
            "redirect_uri": self._meta_redirect_uri(), "code": code}).json()
        if "access_token" not in token:
            raise UserError(_("Meta did not return a token: %s", token.get("error", {}).get("message", token)))
        access = token["access_token"]
        debug = requests.get(f"{GRAPH}/debug_token", timeout=TIMEOUT, params={
            "input_token": access, "access_token": f"{self.meta_app_id}|{sudo.app_secret}"}).json().get("data", {})
        waba_ids = [i for s in debug.get("granular_scopes", []) if s.get("scope") == "whatsapp_business_management"
                    for i in s.get("target_ids", [])]
        if not waba_ids:
            raise UserError(_("The Meta authorization did not grant a WhatsApp Business Account."))
        numbers = self._graph("GET", f"{waba_ids[0]}/phone_numbers", token=access,
                              params={"fields": "id,display_phone_number,verified_name"}).json().get("data", [])
        if not numbers:
            raise UserError(_("The WhatsApp Business Account has no phone number yet."))
        sudo.write({"token": access, "waba_id": waba_ids[0], "phone_number_id": numbers[0]["id"],
                    "display_number": numbers[0].get("display_phone_number"), "state": "connected",
                    "provider": "cloud", "oauth_state": False, "last_error": False})
        self._graph("POST", f"{waba_ids[0]}/subscribed_apps")  # deliver this WABA's messages to our webhook
        return True

    def action_send_test(self):
        """Settings button: proves the connection without sending anything."""
        self.ensure_one()
        if self.provider == "qr":
            self.action_qr_refresh()
            message = _("Gateway: %s", dict(self._fields["state"].selection).get(self.state))
        else:
            info = self._graph("GET", self.phone_number_id, params={"fields": "display_phone_number,verified_name"}).json()
            self.write({"display_number": info.get("display_phone_number"), "state": "connected"})
            message = _("Connected: %s", info.get("verified_name") or self.display_number)
        return {"type": "ir.actions.client", "tag": "display_notification", "params": {"type": "success", "message": message}}

    # ================================================================== sending (both providers)
    def _send_text(self, to, text):
        self.ensure_one()
        if self.provider == "qr":
            return self._gateway("POST", f"/sessions/{self._session_id()}/send", {"to": to, "text": text[:4096]})["id"]
        payload = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to,
                   "type": "text", "text": {"preview_url": False, "body": text[:4096]}}
        return self._graph("POST", f"{self.phone_number_id}/messages", json=payload).json()["messages"][0]["id"]
