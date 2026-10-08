"""Meta WhatsApp Cloud API webhook: verification (GET) and signed notifications (POST)."""
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

MEDIA_KINDS = ("image", "document", "audio", "video", "sticker")


class GsWhatsappWebhook(http.Controller):

    @http.route("/getupsoft_whatsapp/webhook", type="http", auth="public", methods=["GET"], csrf=False)
    def verify(self, **params):
        account = request.env["gs.whatsapp.account"]._by_verify_token(params.get("hub.verify_token"))
        if params.get("hub.mode") == "subscribe" and account:
            return request.make_response(params.get("hub.challenge", ""), [("Content-Type", "text/plain")])
        return request.make_response("forbidden", status=403)

    @http.route("/getupsoft_whatsapp/webhook", type="http", auth="public", methods=["POST"], csrf=False)
    def receive(self):
        raw = request.httprequest.get_data()
        try:
            payload = json.loads(raw or b"{}")
        except ValueError:
            return request.make_response("bad request", status=400)
        Account = request.env["gs.whatsapp.account"].sudo()
        signature = request.httprequest.headers.get("X-Hub-Signature-256", "")
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value") or {}
                number_id = (value.get("metadata") or {}).get("phone_number_id")
                account = Account.search([("phone_number_id", "=", number_id)], limit=1)
                if not account:
                    continue
                if not account._signature_ok(raw, signature):
                    _logger.warning("getupsoft_whatsapp: bad signature for number %s", number_id)
                    return request.make_response("forbidden", status=403)
                names = {c.get("wa_id"): (c.get("profile") or {}).get("name") for c in value.get("contacts", [])}
                for msg in value.get("messages", []):
                    self._handle(account, msg, names.get(msg.get("from")))
        return request.make_response("ok")

    def _handle(self, account, msg, profile_name):
        Message = request.env["gs.whatsapp.message"].sudo()
        if Message.search_count([("wa_message_id", "=", msg.get("id"))]):
            return  # Meta retries: never process a message twice
        conv = request.env["gs.whatsapp.conversation"].sudo()._for_number(account, msg["from"], profile_name)
        kind = msg.get("type", "text")
        if kind == "text":
            conv._receive(msg["id"], "text", text=(msg.get("text") or {}).get("body", ""))
        elif kind in MEDIA_KINDS:
            media = msg[kind]
            data, mimetype = account._download_media(media["id"])
            extension = (mimetype.split("/")[-1].split(";")[0] or "bin").replace("jpeg", "jpg")
            name = media.get("filename") or f"whatsapp_{kind}.{extension}"
            conv._receive(msg["id"], kind, text=media.get("caption", ""), media=(name, data, mimetype))
        else:
            conv._receive(msg["id"], kind, text=f"[{kind}]")
