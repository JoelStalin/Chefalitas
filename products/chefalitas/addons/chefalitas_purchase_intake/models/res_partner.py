from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    purchase_intake_allowed = fields.Boolean(
        "Puede enviar facturas de compra por WhatsApp",
        help="Only WhatsApp messages from these contacts create purchase intakes; everything else is ignored.")
