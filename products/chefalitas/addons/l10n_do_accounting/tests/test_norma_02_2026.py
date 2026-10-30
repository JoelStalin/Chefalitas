from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from . import common


@tagged("-at_install", "post_install")
class Norma022026Test(common.L10nDOTestsCommon):
    """DGII Norma General 02-2026: no N02-05 ITBIS withholding to legal entities that bill with e-CF."""

    def _bill(self, partner, doc_key, number, date="2026-10-01"):
        bill = self._create_l10n_do_invoice(
            data={"partner": partner, "document_type": self.do_document_type[doc_key],
                  "document_number": number, "expense_type": "02", "invoice_date": date},
            invoice_type="in_invoice",
        )
        ret = self.env["account.chart.template"].with_company(self.do_company).ref("ret_30_tax_moral")
        bill.invoice_line_ids.tax_ids |= ret
        return bill

    def test_legal_entity_with_ecf_after_norma_is_blocked(self):
        bill = self._bill(self.fiscal_partner, "e-fiscal", "E310000000077")
        with self.assertRaises(UserError) as cm:
            bill.action_post()
        self.assertIn("02-2026", str(cm.exception))

    def test_before_norma_or_paper_ncf_keeps_withholding(self):
        before = self._bill(self.fiscal_partner, "e-fiscal", "E310000000078", date="2026-09-15")
        self.assertFalse(before._l10n_do_norma_02_2026_applies())
        paper = self._bill(self.fiscal_partner, "fiscal", "B0100000078")
        self.assertFalse(paper._l10n_do_norma_02_2026_applies())

    def test_individual_supplier_keeps_withholding(self):
        bill = self._bill(self.consumo_partner, "e-fiscal", "E310000000079")
        self.assertFalse(bill._l10n_do_norma_02_2026_applies())  # cedula (persona fisica)
