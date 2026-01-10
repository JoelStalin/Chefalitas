import base64
import os

from odoo import fields, models
from odoo.exceptions import AccessError
from odoo.modules.module import get_module_resource


class PosConfig(models.Model):
    _inherit = 'pos.config'

    pos_client_printer_ids = fields.Many2many(
        'pos_client_printer.printer',
        string='Impresoras Avanzadas',
    )
    pos_client_printer_agent_attachment_id = fields.Many2one(
        'ir.attachment',
        string='Instalador del agente',
        readonly=True,
        copy=False,
    )
    pos_client_printer_download_url = fields.Char(string='URL de descarga', readonly=True)

    def action_generate_agent(self):
        if not self.env.user.has_group('base.group_system'):
            raise AccessError('Solo los administradores pueden generar el instalador.')
        installer_path = get_module_resource(
            'pos_client_printer',
            'agent',
            'pos_agent_installer.msi',
        )
        if not installer_path or not os.path.exists(installer_path):
            return False
        with open(installer_path, 'rb') as installer:
            installer_data = base64.b64encode(installer.read())
        for config in self:
            attachment = config.pos_client_printer_agent_attachment_id
            values = {
                'name': 'pos_agent_installer.msi',
                'type': 'binary',
                'datas': installer_data,
                'mimetype': 'application/octet-stream',
                'res_model': 'pos.config',
                'res_id': config.id,
            }
            if attachment:
                attachment.write(values)
            else:
                attachment = self.env['ir.attachment'].create(values)
                config.pos_client_printer_agent_attachment_id = attachment.id
            config.pos_client_printer_download_url = (
                f'/web/content/{attachment.id}?download=true'
            )
        return True
