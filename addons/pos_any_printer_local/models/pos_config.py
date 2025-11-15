
from odoo import models, fields

class PosConfig(models.Model):
    _inherit = 'pos.config'

    enable_local_printing = fields.Boolean(
        'Activar Impresión Local',
        help='Habilita la comunicación con el agente de impresión local a través de WebSockets.'
    )
    local_printer_name = fields.Char(
        'Nombre de la Impresora Local',
        help='El nombre exacto de la impresora tal como aparece en el sistema operativo del cliente (ej. "EPSON TM-T20II").',
        default=''
    )
