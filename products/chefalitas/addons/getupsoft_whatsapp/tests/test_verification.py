import base64
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

VERIF = "odoo.addons.getupsoft_whatsapp.models.verification.requests"
ACCOUNT = "odoo.addons.getupsoft_whatsapp.models.whatsapp_account.requests"


def _resp(body=None):
    r = MagicMock()
    r.json.return_value = body or {}
    r.status_code = 200
    return r


def _b64(text):
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


@tagged("post_install", "-at_install")
class TestMetaCredentialsAndCodes(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Account = cls.env["gs.whatsapp.account"]
        cls.notifier = Account.create({"name": "Compras QR", "provider": "qr", "gateway_url": "http://gw.test",
                                       "gateway_token": "g", "gateway_session": "odoo-x-1"})
        cls.notifier.state = "connected"
        cls.inbox = cls.env["gs.mail.inbox"].create({"name": "Correo Chefalitas", "google_client_id": "cid",
                                                     "google_client_secret": "csecret"})
        cls.meta = Account.create({"name": "Meta Chefalitas", "provider": "cloud", "meta_email": "chefalitas@example.com",
                                   "meta_password": "Cl@ve-Secreta1", "meta_sms_number": "+18095550000",
                                   "code_inbox_id": cls.inbox.id, "notify_account_id": cls.notifier.id,
                                   "notify_number": "+1 809 555 0101"})

    def test_meta_password_is_stored_encrypted(self):
        stored = self.meta.sudo().meta_password_enc
        self.assertTrue(stored)
        self.assertNotIn("Cl@ve-Secreta1", stored)
        self.assertEqual(self.meta.meta_password, "********")
        self.assertEqual(self.meta._meta_credentials(), {"email": "chefalitas@example.com", "password": "Cl@ve-Secreta1"})
        self.assertNotIn("csecret", self.inbox.sudo().google_client_secret_enc)

    def test_google_consent_links_the_mailbox(self):
        action = self.inbox.action_connect_google()
        self.assertIn("accounts.google.com", action["url"])
        self.assertIn("gmail.readonly", action["url"])
        with patch(VERIF + ".post", return_value=_resp({"refresh_token": "RT", "access_token": "AT"})), \
             patch(VERIF + ".get", return_value=_resp({"emailAddress": "chefalitas@gmail.com"})):
            self.inbox._google_complete("CODE")
        self.assertEqual((self.inbox.email, self.inbox.connected), ("chefalitas@gmail.com", True))
        self.assertNotIn("RT", self.inbox.sudo().refresh_token_enc)

    def _link_inbox(self):
        from odoo.addons.getupsoft_whatsapp.models.verification import encrypt
        self.inbox.sudo().refresh_token_enc = encrypt(self.env, "RT")

    def test_email_code_is_found_in_the_mailbox(self):
        self._link_inbox()
        listing = _resp({"messages": [{"id": "m1"}]})
        message = _resp({"snippet": "Tu código de confirmación de Meta", "payload": {"mimeType": "multipart/alternative", "parts": [
            {"mimeType": "text/html", "body": {"data": _b64("<p>Usa el código <b>482913</b> para confirmar.</p>")}}]}})
        with patch(VERIF + ".post", return_value=_resp({"access_token": "AT"})), \
             patch(VERIF + ".get", side_effect=[listing, message]) as get:
            req_id = self.meta.request_code("email", "Meta")
        self.assertIn("from:(facebookmail.com OR meta.com) after:", get.call_args_list[0].kwargs["params"]["q"])
        self.assertEqual(self.meta.get_code(req_id), "482913")

    def test_sms_code_is_asked_over_whatsapp_and_the_reply_is_captured(self):
        sent = []
        with patch(ACCOUNT + ".request", side_effect=lambda m, url, **kw: (sent.append(kw["json"]), _resp({"id": f"O{len(sent)}"}))[1]):
            req_id = self.meta.request_code("sms", "Meta")
            self.assertIsNone(self.meta.get_code(req_id))
            self.assertEqual(sent[0]["to"], "18095550101")
            self.assertIn("+18095550000", sent[0]["text"])
            conv = self.env["gs.whatsapp.conversation"].search([("account_id", "=", self.notifier.id), ("wa_number", "=", "18095550101")])
            conv._receive("IN1", "text", text="codigo 735190")
        self.assertEqual(self.meta.get_code(req_id), "735190")
        self.assertIn("Código recibido", sent[-1]["text"])

    def test_code_can_be_typed_in_odoo(self):
        with patch(ACCOUNT + ".request", return_value=_resp({"id": "O1"})):
            req_id = self.meta.request_code("other", "Meta")
        self.env["gs.verification.request"].browse(req_id).write({"code": "111222", "state": "received"})
        self.assertEqual(self.meta.get_code(req_id), "111222")

    def test_clear_errors_when_nothing_can_deliver_the_code(self):
        bare = self.env["gs.whatsapp.account"].create({"name": "Sin config", "provider": "cloud"})
        with self.assertRaises(UserError):
            bare.request_code("email")
        with self.assertRaises(UserError):
            bare.request_code("sms")
