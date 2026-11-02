from itertools import count
from unittest.mock import patch

from odoo import fields
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


    # ------------------------------------------------------------------ buyer-issued e-CF (vendor bills)

    def _bill(self, doc_key, partner, price=1000.0, taxes=None):
        bill = self._create_l10n_do_invoice(
            data={"partner": partner, "document_type": self.do_document_type[doc_key], "expense_type": "02",
                  "invoice_date": fields.Date.today()},
            invoice_type="in_invoice")
        bill.invoice_line_ids.write({"price_unit": price, "tax_ids": [(6, 0, (taxes or self.env["account.tax"]).ids)]})
        return bill

    def test_07_e41_compra_informal_issued_by_chefalitas(self):
        bill = self._bill("e-informal", self.consumo_partner)
        bill.action_post()
        self.assertEqual(bill.state, "posted")
        self.assertEqual(bill.l10n_do_fiscal_number, "E410000000001")
        self.assertEqual(bill.display_name, "E410000000001")
        self.assertTrue(bill.name.startswith("BILL/"), "internal name stays the journal sequence")
        self.assertEqual(bill.l10n_do_easycount_status, "Aceptado")
        payload = self.fake.issued[0]
        self.assertEqual((payload["eCfType"], payload["encf"], payload["buyerRnc"]), ("E41", "E410000000001", "22400559690"))

    def test_08_e43_gasto_menor_has_no_buyer(self):
        bill = self._bill("e-minor", self.consumo_partner, price=450.0)
        bill.action_post()
        self.assertEqual(bill.l10n_do_fiscal_number, "E430000000001")
        self.assertIsNone(self.fake.issued[0]["buyerRnc"])

    def test_09_e47_pago_exterior_uses_foreign_id(self):
        bill = self._bill("e-exterior", self.foreigner_partner, price=5900.0)
        bill.action_post()
        self.assertEqual(bill.l10n_do_fiscal_number, "E470000000001")
        payload = self.fake.issued[0]
        self.assertEqual((payload["buyerRnc"], payload["buyerForeignId"]), (None, "847898798"))

    def test_10_supplier_ncf_bills_are_not_sent(self):
        bill = self._create_l10n_do_invoice(
            data={"partner": self.fiscal_partner, "document_type": self.do_document_type["fiscal"],
                  "document_number": "B0100000099", "expense_type": "02",
                  "invoice_date": fields.Date.today()}, invoice_type="in_invoice")
        bill.action_post()
        self.assertEqual(bill.l10n_do_fiscal_number, "B0100000099")
        self.assertFalse(self.fake.issued)


    def test_11_easycount_ecf_never_asks_for_a_first_number(self):
        """Live browser finding: the first E31 of the journal required a manual Document Number."""
        for doc_key, partner, move_type in (("e-fiscal", self.fiscal_partner, "out_invoice"),
                                            ("e-informal", self.consumo_partner, "in_invoice")):
            journal = self.fiscal_sale_journal if move_type == "out_invoice" else self.fiscal_purchase_journal
            move = self.env["account.move"].new({
                "move_type": move_type, "journal_id": journal.id, "partner_id": partner.id,
                "l10n_latam_document_type_id": self.do_document_type[doc_key].id,
            })
            self.assertTrue(move._l10n_do_numbered_by_easycount())
            self.assertFalse(move.l10n_do_enable_first_sequence, doc_key)
        paper = self.env["account.move"].new({
            "move_type": "out_invoice", "journal_id": self.fiscal_sale_journal.id, "partner_id": self.fiscal_partner.id,
            "l10n_latam_document_type_id": self.do_document_type["fiscal"].id,
        })
        self.assertFalse(paper._l10n_do_numbered_by_easycount())

    # ------------------------------------------------------------------ partial credit notes keep ITBIS

    def _partial_refund(self, invoice, **wizard_vals):
        wizard = self.env["account.move.reversal"].with_context(
            active_ids=invoice.ids, active_model="account.move").create({
                "journal_id": invoice.journal_id.id,
                "l10n_latam_document_type_id": self.do_document_type["e-credit_note"].id,
                **wizard_vals,
            })
        return self.env["account.move"].browse(wizard.reverse_moves()["res_id"])

    def _posted_e31(self, days_ago=0):
        invoice = self._invoice("e-fiscal", self.fiscal_partner)
        invoice.invoice_date = fields.Date.add(fields.Date.today(), days=-days_ago)
        invoice.invoice_line_ids.write({"price_unit": 1000.0, "quantity": 1,
                                        "tax_ids": [(6, 0, self.do_company.account_sale_tax_id.ids)]})
        invoice.action_post()
        return invoice

    def test_12_fixed_amount_credit_note_carries_the_invoice_itbis(self):
        """Live finding: an E34 for a fixed amount went out without ITBIS."""
        refund = self._partial_refund(self._posted_e31(), l10n_do_refund_type="fixed_amount", l10n_do_amount=100.0)
        self.assertEqual(refund.amount_untaxed, 100.0)
        self.assertEqual(refund.amount_tax, 18.0)
        self.assertEqual(refund.amount_total, 118.0)

    def test_13_percentage_credit_note_keeps_each_tax_group(self):
        invoice = self._invoice("e-fiscal", self.fiscal_partner)
        invoice.invoice_line_ids.write({"price_unit": 1000.0, "quantity": 1,
                                        "tax_ids": [(6, 0, self.do_company.account_sale_tax_id.ids)]})
        invoice.write({"invoice_line_ids": [(0, 0, {"name": "Exento", "price_unit": 500.0, "quantity": 1, "tax_ids": []})]})
        invoice.action_post()
        refund = self._partial_refund(invoice, l10n_do_refund_type="percentage", l10n_do_percentage=10)
        self.assertEqual(refund.amount_untaxed, 150.0)
        self.assertEqual(refund.amount_tax, 18.0, "ITBIS only on the taxed part")

    def test_14_credit_note_after_30_days_does_not_adjust_itbis(self):
        refund = self._partial_refund(self._posted_e31(days_ago=45), l10n_do_refund_type="fixed_amount",
                                      l10n_do_amount=100.0)
        self.assertEqual((refund.amount_untaxed, refund.amount_tax), (100.0, 0.0))
