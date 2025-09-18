from odoo import models, fields


class PosOrder(models.Model):
    _inherit = "pos.order"

    invoice_name = fields.Char(related='account_move.name')
    l10n_latam_document_type_report_name = fields.Char(related='account_move.l10n_latam_document_type_id.report_name')
