from odoo import fields
from odoo.tests import tagged

from odoo.addons.l10n_do_accounting.tests.common import L10nDOTestsCommon


@tagged("post_install", "-at_install")
class TestDgiiReport(L10nDOTestsCommon):

    def test_606_607_generation(self):
        today = fields.Date.today()
        sale = self._create_l10n_do_invoice(data={"invoice_date": today})
        sale.action_post()
        bill = self._create_l10n_do_invoice(
            data={"document_number": "B0100000077", "expense_type": "02", "invoice_date": today},
            invoice_type="in_invoice",
        )
        bill.action_post()

        report = self.env["dgii.reports"].create({
            "name": today.strftime("%m/%Y"),
            "company_id": self.do_company.id,
        })
        report.generate_report()

        self.assertEqual(report.state, "generated")
        # 607: one sale of 100 + 18% ITBIS
        self.assertEqual(report.sale_records, 1)
        self.assertAlmostEqual(report.sale_invoiced_amount, 100.0)
        self.assertAlmostEqual(report.sale_invoiced_itbis, 18.0)
        # 606: one purchase
        self.assertEqual(report.purchase_records, 1)
        # TXT files: DGII header, CRLF line endings
        sale_txt = report.sale_binary.content.decode()
        self.assertTrue(sale_txt.startswith("607|"), sale_txt[:40])
        self.assertIn("\r\n", sale_txt)
        self.assertTrue(report.purchase_binary.content.decode().startswith("606|"))
        self.assertTrue(report.sale_filename.startswith("DGII_607_"))
