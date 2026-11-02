from odoo import models
from odoo.tools.image import image_data_uri


class PosOrder(models.Model):
    _inherit = "pos.order"

    def _order_receipt_barcode_value(self):
        """Lo que codifica el código de barras del recibo: la referencia del pedido, tal cual la busca la pantalla de pedidos."""
        self.ensure_one()
        return (self.pos_reference or "").strip()

    def _order_receipt_generate_barcode(self):
        value = self._order_receipt_barcode_value()
        if not value:
            return False
        png = self.env["ir.actions.report"].barcode("Code128", value, width=450, height=70, humanreadable=1, quiet=1)
        return image_data_uri(png)

    def order_receipt_generate_data(self, basic_receipt=False):
        data = super().order_receipt_generate_data(basic_receipt=basic_receipt)
        data["image"]["order_barcode"] = self._order_receipt_generate_barcode()
        return data
