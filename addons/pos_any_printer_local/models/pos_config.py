from odoo import models, fields

class PosConfig(models.Model):
    _inherit = 'pos.config'

    enable_local_printing = fields.Boolean(string='Activar Impresión Local')
    local_printer_name = fields.Char(string='Nombre impresora local',
                                     help='Nombre de la impresora en la máquina del cliente (ej: "EPSON TM-T20").')
