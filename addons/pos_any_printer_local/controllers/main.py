from odoo import http, api, SUPERUSER_ID
from odoo.http import request

class PosPrintProxy(http.Controller):
    @http.route('/pos_local_printer/ping', type='json', auth='user')
    def ping(self):
        return {'result': 'ok'}

    # Save selected printer name for a given pos.config id
    @http.route('/pos_local_printer/save_printer', type='json', auth='user', methods=['POST'])
    def save_printer(self, pos_config_id=None, printer_name=None):
        if not pos_config_id or not printer_name:
            return {'result': 'error', 'error': 'Falta pos_config_id o printer_name'}
        try:
            env = request.env
            cfg = env['pos.config'].sudo().browse(int(pos_config_id))
            if not cfg.exists():
                return {'result': 'error', 'error': 'pos.config no encontrado'}
            cfg.sudo().write({'local_printer_name': printer_name})
            return {'result': 'ok'}
        except Exception as e:
            return {'result': 'error', 'error': str(e)}

    # Nota: no usamos este endpoint para imprimir localmente. Es sólo de control/fallback si lo deseas.
    @http.route('/pos_local_printer/server_print', type='json', auth='user')
    def server_print(self, data):
        # Ejemplo: permitir al servidor imprimir si config lo requiere
        return {'result': 'server_not_implemented'}
