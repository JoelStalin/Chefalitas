from odoo import models, fields

class PosConfig(models.Model):
    _inherit = 'pos.config'

    local_printer_name = fields.Char(string='Nombre impresora local',
                                     help='Nombre de la impresora en la máquina del cliente (ej: "EPSON TM-T20").')
