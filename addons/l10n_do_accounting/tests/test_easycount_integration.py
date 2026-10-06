from itertools import count
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged

from . import common
from ..models.easycount_client import EasyCountError


class FakeEasyCount:
    """Stand-in for EasyCountClient: numbers per type, scripted DGII answers."""

    def __init__(self):
        self.seqs = {}
        self.issued = []
        self.reject = None
        self.offline = False

    def allocate_encf(self, e_cf_type):
        seq = self.seqs.setdefault(e_cf_type, count(1))
        return f"{e_cf_type}{next(seq):010d}"

    def issue(self, payload):
        if self.offline:
            raise EasyCountError("No se pudo conectar con EasyCount: refused")
        self.issued.append(payload)
        if self.reject:
            code, text = self.reject
            return {"encf": payload["encf"], "accepted": False, "status": "Rechazado",
                    "messages": [{"codigo": code, "valor": text}]}
        return {
            "encf": payload["encf"], "trackId": f"TRK-{len(self.issued)}", "status": "Aceptado",
            "accepted": True, "messages": [], "securityCode": "ABC123", "emulated": True,
            "xml": f"<ECF><eNCF>{payload['encf']}</eNCF></ECF>",
        }


@tagged("-at_install", "post_install")
class EasyCountIntegrationTest(common.L10nDOTestsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.do_company.write({
            "l10n_do_ecf_issuer": True,
            "l10n_do_easycount_enabled": True,
            "l10n_do_easycount_url": "http://easycount.test",
            "l10n_do_easycount_token": "tok-test",
        })

    def setUp(self):
        super().setUp()
        self.fake = FakeEasyCount()
        patcher = patch.object(
            type(self.env["res.company"]), "_l10n_do_easycount_client", lambda company: self.fake
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _invoice(self, doc_key, partner):
        return self._create_l10n_do_invoice(
            data={"partner": partner, "document_type": self.do_document_type[doc_key]}
        )

    def test_01_e31_gets_encf_from_easycount_and_stores_dgii_result(self):
        invoice = self._invoice("e-fiscal", self.fiscal_partner)
        invoice.action_post()
        self.assertEqual(invoice.state, "posted")
        self.assertEqual(invoice.l10n_do_fiscal_number, "E310000000001")
        self.assertEqual(invoice.l10n_do_easycount_track_id, "TRK-1")
        self.assertEqual(invoice.l10n_do_easycount_status, "Aceptado")
        self.assertEqual(invoice.l10n_do_ecf_security_code, "ABC123")
        self.assertTrue(invoice.l10n_do_easycount_emulated)
        self.assertTrue(invoice.l10n_do_ecf_edi_file)
        payload = self.fake.issued[0]
        self.assertEqual((payload["eCfType"], payload["encf"]), ("E31", "E310000000001"))
        self.assertEqual(payload["buyerRnc"], "131566332")

    def test_02_each_customer_type_uses_its_own_sequence(self):
        cases = [
            ("e-fiscal", self.fiscal_partner, "E31"),
            ("e-consumer", self.consumo_partner, "E32"),
            ("e-special", self.special_partner, "E44"),
            ("e-governmental", self.gov_partner, "E45"),
        ]
        for doc_key, partner, prefix in cases:
            with self.subTest(prefix=prefix):
                invoice = self._invoice(doc_key, partner)
                invoice.action_post()
                self.assertEqual(invoice.l10n_do_fiscal_number, f"{prefix}0000000001")
                self.assertEqual(invoice.l10n_do_easycount_status, "Aceptado")
        self.assertEqual([p["eCfType"] for p in self.fake.issued], [c[2] for c in cases])

    def test_03_dgii_rejection_raises_and_reverts_post(self):
        self.fake.reject = (150, "MontoTotal declarado no cuadra")
        invoice = self._invoice("e-fiscal", self.fiscal_partner)
        with self.assertRaises(UserError) as cm:
            invoice.action_post()
        self.assertIn("150", str(cm.exception))
        invoice.invalidate_recordset()
        self.assertEqual(invoice.state, "draft")
        self.assertFalse(invoice.l10n_do_easycount_track_id)

    def test_04_deferred_company_keeps_invoice_pending_when_offline(self):
        self.do_company.l10n_do_ecf_deferred_submissions = True
        self.fake.offline = True
        invoice = self._invoice("e-fiscal", self.fiscal_partner)
        invoice.action_post()
        self.assertEqual(invoice.state, "posted")
        self.assertTrue(invoice.l10n_do_easycount_pending)
        self.fake.offline = False
        invoice.action_l10n_do_easycount_retry()
        self.assertFalse(invoice.l10n_do_easycount_pending)
        self.assertEqual(invoice.l10n_do_easycount_status, "Aceptado")

    def test_05_offline_without_deferred_mode_blocks_post(self):
        self.fake.offline = True
        invoice = self._invoice("e-fiscal", self.fiscal_partner)
        with self.assertRaises(UserError):
            invoice.action_post()

    def test_06_disabled_company_never_calls_easycount(self):
        self.do_company.l10n_do_easycount_enabled = False
        invoice = self._invoice("e-fiscal", self.fiscal_partner)
        invoice.action_post()
        self.assertEqual(self.fake.issued, [])
        self.assertFalse(invoice.l10n_do_easycount_track_id)
