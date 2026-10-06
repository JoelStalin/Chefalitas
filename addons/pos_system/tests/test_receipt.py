from odoo.tests import TransactionCase, tagged


class _Data(dict):
    """Receipt data dict: keys the header does not need here read as False."""

    def __missing__(self, key):
        return False


@tagged("post_install", "-at_install")
class TestDoReceipt(TransactionCase):

    def _values(self, **extra):
        return {
            "image": _Data(logo=False),
            "extra_data": _Data(formated_date_order="06/10/2026", cashier_name="Ana",
                                partner_vat_label="RNC", **extra),
            "partner": False,
            "order": _Data(tracking_number="001"),
            "conditions": _Data(),
            "config": _Data(),
            "company": _Data(),
        }

    def _render(self, **extra):
        return str(self.env["ir.qweb"]._render("point_of_sale.pos_order_receipt_header", self._values(**extra)))

    def test_header_prints_document_type_and_ncf(self):
        html = self._render(l10n_do_document_type="Factura de Credito Fiscal Electronica", l10n_do_ncf="E310000000001")
        self.assertIn("E310000000001", html)
        self.assertIn("Factura de Credito Fiscal Electronica", html)

    def test_header_without_invoice_has_no_fiscal_block(self):
        self.assertNotIn("l10n-do-ncf", self._render())
