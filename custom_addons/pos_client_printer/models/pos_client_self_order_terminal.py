from odoo import fields, models


class PosClientSelfOrderTerminal(models.Model):
    _name = 'pos_client_printer.self_order_terminal'
    _description = 'POS Client Printer Self Order Terminal'

    name = fields.Char(required=True)
    pos_config_id = fields.Many2one('pos.config', required=True)
    active = fields.Boolean(default=True)
