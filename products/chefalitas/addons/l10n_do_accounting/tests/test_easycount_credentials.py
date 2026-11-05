import base64
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import BinaryBytes

from . import common
from ..models.easycount_client import EasyCountError


class FakeCredentials:
    def __init__(self):
        self.uploaded = []
        self.fail = None

    def get_credentials(self):
        return {"configured": False, "rnc": "131793916"}

    def upload_credentials(self, payload):
        if self.fail:
            raise EasyCountError(self.fail, 400)
        self.uploaded.append(payload)
        return {"configured": True, "cert_subject": "ANA MERCEDES MARTINEZ ESPINAL", "cert_not_after": "2027-10-07T00:00:00Z"}


@tagged("-at_install", "post_install")
class EasyCountCredentialsTest(common.L10nDOTestsCommon):
    def setUp(self):
        super().setUp()
        self.fake = FakeCredentials()
        patcher = patch.object(type(self.env["res.company"]), "_l10n_do_easycount_client", lambda company: self.fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.company = self.do_company
        self.Wizard = self.env["l10n_do.easycount.credentials.wizard"].with_company(self.company)

    def _wizard(self, **vals):
        return self.Wizard.create({"p12_file": BinaryBytes(b"P12-BYTES", "cert.p12"), "p12_password": "Clave#1",
                                   "portal_password": "Pórtal+2", **vals})

    def test_01_sends_company_data_and_secrets_then_forgets_them(self):
        wizard = self._wizard()
        self.assertEqual(wizard.portal_user, self.company.vat)
        self.assertIn("Sin credenciales", wizard.status_text)
        action = wizard.action_send()
        sent = self.fake.uploaded[0]
        self.assertEqual(sent["company_name"], self.company.name)
        self.assertEqual(base64.b64decode(sent["p12_base64"]), b"P12-BYTES")
        self.assertEqual((sent["p12_password"], sent["portal_password"]), ("Clave#1", "Pórtal+2"))
        self.assertEqual(action["params"]["type"], "success")
        self.assertFalse(wizard.p12_file or wizard.p12_password or wizard.portal_password)

    def test_02_keeps_the_portal_password_in_easycount_when_left_empty(self):
        self._wizard(portal_password=False).action_send()
        self.assertNotIn("portal_password", self.fake.uploaded[0])

    def test_03_easycount_rejection_is_shown_and_secrets_are_still_wiped(self):
        self.fake.fail = "El certificado es de OTRA SRL"
        wizard = self._wizard()
        with self.assertRaisesRegex(UserError, "OTRA SRL"):
            wizard.action_send()

    def test_04_requires_certificate_and_password(self):
        with self.assertRaises(UserError):
            self.Wizard.create({"p12_password": "x"}).action_send()
