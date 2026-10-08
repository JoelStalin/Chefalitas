"""WhatsApp Business account (Meta Cloud API, Graph API). Written by GetUpSoft from Meta's public documentation."""
import hashlib
import hmac
import logging
import secrets

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

GRAPH = "https://graph.facebook.com/v21.0"
TIMEOUT = 20


class GsWhatsappAccount(models.Model):
    _name = "gs.whatsapp.account"
    _description = "WhatsApp Business account"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    phone_number_id = fields.Char("Phone number ID", required=True, help="Meta: WhatsApp > API setup > Phone number ID")
    display_number = fields.Char("Number shown to customers")
    token = fields.Char("Access token", required=True, groups="base.group_system", copy=False)
    app_secret = fields.Char("App secret", required=True, groups="base.group_system", copy=False,
                             help="Used to check the X-Hub-Signature-256 of every webhook call")
    verify_token = fields.Char("Webhook verify token", required=True, copy=False, groups="base.group_system",
                               default=lambda self: secrets.token_urlsafe(24))
    webhook_url = fields.Char(compute="_compute_webhook_url")

    def _compute_webhook_url(self):
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        for account in self:
            account.webhook_url = f"{base}/getupsoft_whatsapp/webhook"

    # ------------------------------------------------------------------ webhook security
    @api.model
    def _by_verify_token(self, token):
        return self.sudo().search([("verify_token", "=", token)], limit=1) if token else self.browse()

    def _signature_ok(self, body: bytes, header: str) -> bool:
        """Meta signs the raw body with the app secret: X-Hub-Signature-256: sha256=<hex>."""
        self.ensure_one()
        if not header or not header.startswith("sha256="):
            return False
        expected = hmac.new(self.sudo().app_secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, header[7:])

    # ------------------------------------------------------------------ Graph API
    def _graph(self, method, path, **kwargs):
        self.ensure_one()
        try:
            response = requests.request(method, f"{GRAPH}/{path}", timeout=TIMEOUT,
                                        headers={"Authorization": f"Bearer {self.sudo().token}"}, **kwargs)
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

    def _send_text(self, to_number, text):
        payload = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to_number,
                   "type": "text", "text": {"preview_url": False, "body": text[:4096]}}
        return self._graph("POST", f"{self.phone_number_id}/messages", json=payload).json()["messages"][0]["id"]

    def action_send_test(self):
        """Settings button: proves token and number id are valid without sending anything."""
        self.ensure_one()
        info = self._graph("GET", self.phone_number_id, params={"fields": "display_phone_number,verified_name"}).json()
        self.display_number = info.get("display_phone_number")
        return {"type": "ir.actions.client", "tag": "display_notification", "params": {
            "type": "success", "message": _("Connected: %s", info.get("verified_name") or self.display_number)}}
