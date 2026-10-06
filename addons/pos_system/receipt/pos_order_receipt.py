from odoo import models


class PosOrderReceipt(models.AbstractModel):
    _inherit = "pos.order.receipt"

    def order_receipt_generate_data(self, basic_receipt=False):
        """DGII printed representation: document type and NCF/e-NCF in the receipt header
        (Informe Tecnico e-CF v1.0, s.17.2.1)."""
        data = super().order_receipt_generate_data(basic_receipt)
        move = self.account_move
        data["extra_data"]["l10n_do_document_type"] = move.l10n_latam_document_type_id.report_name or False
        data["extra_data"]["l10n_do_ncf"] = (move.l10n_do_fiscal_number if "l10n_do_fiscal_number" in move._fields else False) or move.name or False
        qr_url = (data["order"].get("l10n_do_receipt") or {}).get("qr_url")
        data["image"]["l10n_do_qr"] = self._order_receipt_generate_qr_code(qr_url) if qr_url else False
        return data
