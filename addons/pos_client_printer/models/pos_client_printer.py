from odoo import api, fields, models


class PosClientPrinter(models.Model):
    _name = 'pos_client_printer.printer'
    _description = 'POS Client Printer'

    name = fields.Char(required=True)
    ip_address = fields.Char(string='Dirección IP')
    printer_type = fields.Selection(
        [
            ('windows', 'Impresora Windows'),
            ('network', 'Impresora de red'),
        ],
        default='windows',
        required=True,
    )
    pos_config_ids = fields.Many2many('pos.config', string='Puntos de Venta')
    token = fields.Char(string='Token de Autenticación', readonly=True, copy=False)

    @api.model
    def create(self, vals):
        if not vals.get('token'):
            vals['token'] = self.env['ir.sequence'].next_by_code('pos_client_printer.printer.token')
        return super().create(vals)
