from odoo import http
from odoo.http import request


class PosClientPrinterController(http.Controller):

    @http.route('/pos_client_printer/get_jobs', type='json', auth='user')
    def get_jobs(self, printer_id, token):
        """Devuelve una lista de pedidos pendientes para la impresora especificada"""
        printer = request.env['pos_client_printer.printer'].sudo().browse(printer_id)
        if not printer or printer.token != token:
            return {'error': 'Token inválido'}
        orders = request.env['pos.order'].sudo().search([
            ('state', '=', 'paid'),
            ('is_printed', '=', False),
        ])
        job_list = []
        for order in orders:
            job_list.append({
                'order_id': order.id,
                'pos_reference': order.pos_reference,
                'receipt_html': order._export_for_printing().get('receipt_html'),
            })
        return {'jobs': job_list}

    @http.route('/pos_client_printer/confirm_print', type='json', auth='user')
    def confirm_print(self, order_id):
        """Marca el pedido como impreso"""
        order = request.env['pos.order'].sudo().browse(order_id)
        order.is_printed = True
        return {'status': 'done'}
