
from odoo import models, fields

class PosConfig(models.Model):
    _inherit = 'pos.config'

    enable_local_printing = fields.Boolean(
        string='Activar Impresión Local (WebSocket)',
        help='Habilita la comunicación con el agente de impresión local para impresiones directas.'
    )
    local_printer_name = fields.Char(
        string='Nombre de la Impresora Local',
        help='El nombre exacto de la impresora en el sistema operativo del cliente (ej. "EPSON TM-T20II").',
        default=''
    )

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_enable_local_printing = fields.Boolean(
        related='pos_config_id.enable_local_printing',
        readonly=False
    )
    pos_local_printer_name = fields.Char(
        related='pos_config_id.local_printer_name',
        readonly=False
    )
