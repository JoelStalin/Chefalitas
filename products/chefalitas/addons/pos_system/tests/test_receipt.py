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

    # ------------------------------------------------------------------ DGII e-CF layout

    def _ecf_receipt(self, **over):
        r = {
            "company": {"name": "Chefalitas", "vat": "1-31-79391-6", "address": "Av. Churchill, Santo Domingo", "phone": "809-555-0199"},
            "document_type": "FACTURA DE CONSUMO ELECTRONICA", "is_ecf": True, "ncf": "E320000000002",
            "date": "06/10/2026 17:16:00", "due_date": False, "register": "Chefalitas Restaurante",
            "order_ref": "261-1-000001", "table": "1", "customer": "CONSUMIDOR FINAL", "customer_vat": "N/A",
            "lines": [{"qty": 1, "name": "Pollo al horno", "itbis": "63.00", "total": "413.00"}],
            "gravado": "350.00", "exento": False, "itbis": "63.00", "itbis_rate": "18%",
            "tip": "35.00", "tip_rate": "10%", "total": "448.00",
            "payments": [{"name": "Cash", "amount": "500.00"}], "change": "52.00",
            "security_code": "A1B2C3", "sign_date": "06/10/2026 17:16:02", "qr_url": "https://ecf.dgii.gov.do/x",
        }
        r.update(over)
        values = self._values()
        values.update(order=_Data(l10n_do_receipt=r), lines=[], payments=[], preset=False,
                      image=_Data(logo=False, l10n_do_qr="data:image/png;base64,AA=="))
        return str(self.env["ir.qweb"]._render("point_of_sale.pos_order_receipt", values))

    def test_invoiced_order_prints_dgii_layout(self):
        html = self._ecf_receipt()
        for text in ("FACTURA DE CONSUMO ELECTRONICA", "(e-CF)", "E320000000002", "RNC: 1-31-79391-6",
                     "CANT", "DESCRIPCION", "SUBTOTAL GRAVADO", "TOTAL ITBIS (18%)", "PROPINA LEGAL (10%)",
                     "TOTAL A PAGAR", "Cambio", "A1B2C3", "Representacion Impresa de e-CF"):
            self.assertIn(text, html)
        self.assertIn('name="l10n_do_qr"', html)
        self.assertNotIn('name="cashier_name"', html, "the generic ticket is replaced")

    def test_takeout_and_paper_ncf_layout(self):
        html = self._ecf_receipt(tip=False, is_ecf=False, ncf="B0200000001", document_type="FACTURA DE CONSUMO",
                                 security_code=False, qr_url=False)
        self.assertNotIn("PROPINA", html)
        self.assertNotIn("Representacion Impresa de e-CF", html)
        self.assertIn("NCF:", html)

    def test_rnc_and_cedula_are_printed_with_dgii_dashes(self):
        from odoo.addons.pos_system.models.pos_order_inherit import _fmt_id
        self.assertEqual(_fmt_id("131793916"), "1-31-79391-6")
        self.assertEqual(_fmt_id("22400559690"), "224-0055969-0")
        self.assertEqual(_fmt_id(False), "")

    def test_ecf_layout_is_sent_to_the_pos(self):
        """The POS renders receipts in the browser with the templates the server sends."""
        self.assertIn("pos_system.l10n_do_ecf_receipt", self.env["ir.ui.view"]._get_xml_ids_to_load())
