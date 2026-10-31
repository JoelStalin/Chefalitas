from odoo import api, models


class IrUiView(models.Model):
    _inherit = "ir.ui.view"

    @api.model
    def _get_xml_ids_to_load(self):
        # the POS renders receipts client-side: it only knows the templates listed here
        return super()._get_xml_ids_to_load() + ["pos_system.l10n_do_ecf_receipt"]
