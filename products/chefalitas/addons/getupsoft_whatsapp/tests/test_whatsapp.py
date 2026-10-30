import base64
import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

from odoo.tests import HttpCase, tagged

ACCOUNT = "odoo.addons.getupsoft_whatsapp.models.whatsapp_account.requests"
SECRET = "app-secret-test"
PNG = b"\x89PNG\r\n\x1a\nfake"


def _response(status=200, body=None, content=b"", headers=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body or {}
    r.content = content
    r.headers = headers or {}
    r.text = json.dumps(body or {})
    return r


@tagged("post_install", "-at_install")
class TestGsWhatsapp(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account = cls.env["gs.whatsapp.account"].create({
            "name": "Chefalitas compras", "provider": "cloud", "phone_number_id": "1234567890", "token": "tok",
            "app_secret": SECRET, "verify_token": "verify-me"})

    def _post(self, payload, secret=SECRET):
        raw = json.dumps(payload).encode()
        signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        return self.url_open("/getupsoft_whatsapp/webhook", data=raw,
                             headers={"Content-Type": "application/json", "X-Hub-Signature-256": signature})

    def _payload(self, messages, name="Karla Caja"):
        return {"entry": [{"changes": [{"value": {
            "metadata": {"phone_number_id": "1234567890"},
            "contacts": [{"wa_id": "18095550101", "profile": {"name": name}}],
            "messages": messages}}]}]}

    def test_meta_verification(self):
        ok = self.url_open("/getupsoft_whatsapp/webhook?hub.mode=subscribe&hub.verify_token=verify-me&hub.challenge=42")
        self.assertEqual((ok.status_code, ok.text), (200, "42"))
        bad = self.url_open("/getupsoft_whatsapp/webhook?hub.mode=subscribe&hub.verify_token=nope&hub.challenge=42")
        self.assertEqual(bad.status_code, 403)

    def test_unsigned_or_wrongly_signed_calls_are_rejected(self):
        payload = self._payload([{"from": "18095550101", "id": "wamid.X1", "type": "text", "text": {"body": "hola"}}])
        self.assertEqual(self._post(payload, secret="other").status_code, 403)
        self.assertFalse(self.env["gs.whatsapp.message"].search_count([("wa_message_id", "=", "wamid.X1")]))

    def test_text_creates_conversation_contact_and_runs_the_hook(self):
        calls = []
        with patch("odoo.addons.getupsoft_whatsapp.models.whatsapp_conversation.GsWhatsappConversation._on_inbound",
                   lambda conv, msg: calls.append(msg.body)):
            res = self._post(self._payload([{"from": "18095550101", "id": "wamid.T1", "type": "text", "text": {"body": "hola"}}]))
        self.assertEqual(res.status_code, 200)
        conv = self.env["gs.whatsapp.conversation"].search([("wa_number", "=", "18095550101")])
        self.assertEqual(conv.partner_id.name, "Karla Caja")
        self.assertEqual(conv.message_ids_wa.body, "hola")
        self.assertEqual(calls, ["hola"])
        self.assertTrue(conv._can_reply_freely())

    def test_image_is_downloaded_and_attached_and_retries_are_ignored(self):
        def graph(method, url, **kwargs):
            return _response(body={"url": "https://lookaside.fbsbx.com/media/1", "mime_type": "image/png"})
        requests_mock = MagicMock()
        requests_mock.request.side_effect = graph
        requests_mock.get.return_value = _response(content=PNG, headers={"Content-Type": "image/png"})
        requests_mock.RequestException = Exception
        message = {"from": "18095550101", "id": "wamid.I1", "type": "image",
                   "image": {"id": "media-1", "mime_type": "image/png", "caption": "factura"}}
        with patch(ACCOUNT, requests_mock):
            self._post(self._payload([message]))
            self._post(self._payload([message]))  # Meta retry
        msgs = self.env["gs.whatsapp.message"].search([("wa_message_id", "=", "wamid.I1")])
        self.assertEqual(len(msgs), 1)
        self.assertEqual((msgs.kind, msgs.body, bytes(msgs.attachment_id.raw), msgs.attachment_id.mimetype),
                         ("image", "factura", PNG, "image/png"))
        self.assertEqual(requests_mock.get.call_args.kwargs["headers"], {"Authorization": "Bearer tok"})

    def test_send_text_calls_the_cloud_api_and_records_it(self):
        conv = self.env["gs.whatsapp.conversation"]._for_number(self.account, "+1 809 555 0102", "Ana")
        with patch(ACCOUNT + ".request", return_value=_response(body={"messages": [{"id": "wamid.OUT1"}]})) as req:
            conv.send_text("Recibido")
        method, url = req.call_args.args
        self.assertEqual((method, url), ("POST", "https://graph.facebook.com/v21.0/1234567890/messages"))
        self.assertEqual(req.call_args.kwargs["json"]["to"], "18095550102")
        self.assertEqual(req.call_args.kwargs["json"]["text"]["body"], "Recibido")
        out = conv.message_ids_wa.filtered(lambda m: m.direction == "out")
        self.assertEqual((out.wa_message_id, out.body), ("wamid.OUT1", "Recibido"))

    def test_works_without_orca(self):
        # orca_bridge is not a dependency: without it inbound messages are stored and nothing fails
        conv = self.env["gs.whatsapp.conversation"]._for_number(self.account, "18095550103")
        message = conv._receive("wamid.N1", "text", text="sin ORCA")
        self.assertEqual(message.body, "sin ORCA")


QR_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="


@tagged("post_install", "-at_install")
class TestGsWhatsappQr(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account = cls.env["gs.whatsapp.account"].create({
            "name": "Grupo compras", "provider": "qr", "gateway_url": "http://gw.test", "gateway_token": "gwtok"})

    def _link(self):
        reply = _response(body={"id": "odoo-chef-1", "status": "qr", "qr": f"data:image/png;base64,{QR_PNG}"})
        with patch(ACCOUNT + ".request", return_value=reply) as req:
            self.account.action_qr_link()
        return req

    def test_qr_link_shows_the_code_and_registers_the_signed_webhook(self):
        req = self._link()
        method, url = req.call_args.args
        self.assertEqual(method, "POST")
        self.assertTrue(url.startswith("http://gw.test/sessions/"))
        body = req.call_args.kwargs["json"]
        self.assertTrue(body["webhook_url"].endswith("/getupsoft_whatsapp/qr_webhook"))
        self.assertEqual(body["webhook_secret"], self.account.gateway_secret)
        self.assertEqual(req.call_args.kwargs["headers"], {"Authorization": "Bearer gwtok"})
        self.assertEqual((self.account.state, self.account.gateway_session), ("qr", "odoo-chef-1"))
        self.assertTrue(self.account.qr_image)

    def _post(self, payload, secret=None):
        raw = json.dumps(payload).encode()
        sig = "sha256=" + hmac.new((secret or self.account.gateway_secret).encode(), raw, hashlib.sha256).hexdigest()
        return self.url_open("/getupsoft_whatsapp/qr_webhook", data=raw,
                             headers={"Content-Type": "application/json", "X-GS-Signature": sig})

    def test_group_message_keeps_its_sender_and_bad_signatures_are_rejected(self):
        self._link()
        payload = {"session": "odoo-chef-1", "id": "G1", "chat": "120363000000@g.us", "group": True,
                   "from": "18095550101", "name": "Karla", "type": "image", "text": "factura",
                   "media": {"mimetype": "image/jpeg", "filename": None, "data": base64.b64encode(b"JPEG").decode()}}
        self.assertEqual(self._post(payload, secret="otro").status_code, 403)
        self.assertEqual(self._post(payload).status_code, 200)
        conv = self.env["gs.whatsapp.conversation"].search([("account_id", "=", self.account.id), ("is_group", "=", True)])
        msg = conv.message_ids_wa
        self.assertEqual((conv.wa_number, msg.author_id.name, msg.body, bytes(msg.attachment_id.raw)),
                         ("120363000000", "Karla", "factura", b"JPEG"))
        self.assertEqual(self._post(payload).status_code, 200)  # gateway retry: not stored twice
        self.assertEqual(len(conv.message_ids_wa), 1)

    def test_replies_go_through_the_gateway_session(self):
        self._link()
        conv = self.env["gs.whatsapp.conversation"]._for_group(self.account, "120363000000@g.us", "Compras")
        with patch(ACCOUNT + ".request", return_value=_response(body={"id": "OUT9"})) as req:
            conv.send_text("Recibida")
        method, url = req.call_args.args
        self.assertEqual((method, url), ("POST", "http://gw.test/sessions/odoo-chef-1/send"))
        self.assertEqual(req.call_args.kwargs["json"], {"to": "120363000000@g.us", "text": "Recibida"})


@tagged("post_install", "-at_install")
class TestGsWhatsappMetaOAuth(HttpCase):

    def test_meta_consent_fills_token_waba_and_number(self):
        account = self.env["gs.whatsapp.account"].create({
            "name": "Meta prueba", "provider": "cloud", "meta_app_id": "111", "meta_config_id": "222", "app_secret": SECRET})
        action = account.action_meta_connect()
        self.assertIn("dialog/oauth", action["url"])
        self.assertIn("config_id=222", action["url"])
        gets = [_response(body={"access_token": "LONG"}),
                _response(body={"data": {"granular_scopes": [{"scope": "whatsapp_business_management", "target_ids": ["WABA1"]}]}})]
        calls = []

        def graph(method, url, **kw):
            calls.append((method, url))
            if url.endswith("/phone_numbers"):
                return _response(body={"data": [{"id": "PN1", "display_phone_number": "+1 555 0100", "verified_name": "Test"}]})
            return _response(body={"success": True})
        with patch(ACCOUNT + ".get", side_effect=gets), patch(ACCOUNT + ".request", side_effect=graph):
            account._meta_complete("CODE")
        self.assertEqual((account.token, account.waba_id, account.phone_number_id, account.state),
                         ("LONG", "WABA1", "PN1", "connected"))
        self.assertIn(("POST", "https://graph.facebook.com/v21.0/WABA1/subscribed_apps"), calls)

    def test_callback_rejects_an_unknown_state(self):
        self.authenticate("admin", "admin")
        res = self.url_open("/getupsoft_whatsapp/meta/callback?code=x&state=999:nope")
        self.assertEqual(res.status_code, 400)
