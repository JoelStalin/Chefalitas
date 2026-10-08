"""Meta WhatsApp Cloud API webhook: verification (GET) and signed notifications (POST)."""
import base64
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


class GsWhatsappQrWebhook(http.Controller):
    """Messages from the GetUpSoft QR gateway, signed with the account's own secret (X-GS-Signature)."""

    @http.route("/getupsoft_whatsapp/qr_webhook", type="http", auth="public", methods=["POST"], csrf=False)
    def receive(self):
        raw = request.httprequest.get_data()
        try:
            msg = json.loads(raw or b"{}")
        except ValueError:
            return request.make_response("bad request", status=400)
        account = request.env["gs.whatsapp.account"].sudo().search(
            [("provider", "=", "qr"), ("gateway_session", "=", msg.get("session"))], limit=1)
        if not account or not account._qr_signature_ok(raw, request.httprequest.headers.get("X-GS-Signature", "")):
            return request.make_response("forbidden", status=403)
        if request.env["gs.whatsapp.message"].sudo().search_count([("wa_message_id", "=", msg.get("id"))]):
            return request.make_response("ok")
        Conv = request.env["gs.whatsapp.conversation"].sudo()
        sender = Conv._partner_for_number(msg.get("from", ""), msg.get("name"))
        conv = Conv._for_group(account, msg["chat"]) if msg.get("group") else Conv._for_number(account, msg["from"], msg.get("name"))
        if not conv.partner_id and not conv.is_group:
            conv.partner_id = sender
        media = None
        if msg.get("media"):
            m = msg["media"]
            ext = (m["mimetype"].split("/")[-1].split(";")[0] or "bin").replace("jpeg", "jpg")
            media = (m.get("filename") or f"whatsapp_{msg.get('type')}.{ext}", base64.b64decode(m["data"]), m["mimetype"])
        conv._receive(msg["id"], msg.get("type", "text"), text=msg.get("text", ""), media=media, author=sender)
        return request.make_response("ok")

    @http.route("/getupsoft_whatsapp/meta/callback", type="http", auth="user", methods=["GET"])
    def meta_callback(self, code=None, state=None, error_description=None, **kwargs):
        account_id = int((state or "0:").split(":")[0] or 0)
        account = request.env["gs.whatsapp.account"].browse(account_id).exists()
        if not account or not state or account.sudo().oauth_state != state:
            return request.make_response("Solicitud de vinculación no válida o vencida.", status=400)
        if not code:
            return request.make_response(f"Meta no autorizó la vinculación: {error_description or ''}", status=400)
        account._meta_complete(code)
        return request.redirect(f"/odoo/action-getupsoft_whatsapp.action_gs_whatsapp_account/{account.id}")


class GsGoogleMailbox(http.Controller):
    @http.route("/getupsoft_whatsapp/google/callback", type="http", auth="user", methods=["GET"])
    def google_callback(self, code=None, state=None, error=None, **kwargs):
        inbox_id = int((state or "0:").split(":")[0] or 0)
        inbox = request.env["gs.mail.inbox"].browse(inbox_id).exists()
        if not inbox or not state or inbox.sudo().oauth_state != state:
            return request.make_response("Solicitud de vinculación no válida o vencida.", status=400)
        if not code:
            return request.make_response(f"Google no autorizó el acceso: {error or ''}", status=400)
        inbox._google_complete(code)
        return request.redirect(f"/odoo/action-getupsoft_whatsapp.action_gs_mail_inbox/{inbox.id}")
