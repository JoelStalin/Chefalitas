from odoo import fields, models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    is_printed = fields.Boolean(default=False)
