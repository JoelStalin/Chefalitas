# -*- coding: utf-8 -*-
import json
import logging
from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

class OrcaBridgeController(http.Controller):

    def _verify_auth(self):
        """Verifies bearer token against ir.config_parameter orca.api_token."""
        auth_header = request.httprequest.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return False
        token = auth_header.split(' ', 1)[1].strip()
        expected = request.env['ir.config_parameter'].sudo().get_param('orca.api_token', 'orca_sec_c9f408e71b26a8d542e19034f8a7')
        return token == expected

    def _json_response(self, data, status=200):
        return Response(
            json.dumps(data, default=str),
            status=status,
            mimetype='application/json'
        )

    def _error(self, message, status=400):
        return self._json_response({'status': 'error', 'message': message}, status=status)

    @http.route('/api/orca/v1/health', type='http', auth='none', methods=['GET'], csrf=False)
    def health(self, **kwargs):
        """Public health check endpoint."""
        return self._json_response({
            'status': 'ok',
            'service': 'orca-odoo-bridge',
            'odoo_version': '18.0',
            'database': request.db or 'chefalitas',
        })

    # ==================== ACCOUNT & DGII e-NCF ====================

    @http.route('/api/orca/v1/account/summary', type='http', auth='none', methods=['GET'], csrf=False)
    def account_summary(self, **kwargs):
        """Returns financial summary: total receivables, payables, and today's sales."""
        if not self._verify_auth():
            return self._error('Unauthorized: Invalid or missing token', 401)

        env = request.env
        invoices = env['account.move'].sudo().search([
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('state', '=', 'posted')
        ])
        total_invoiced = sum(invoices.mapped('amount_total'))
        total_due = sum(invoices.mapped('amount_residual'))

        return self._json_response({
            'status': 'success',
            'total_posted_invoices': len(invoices),
            'total_invoiced': total_invoiced,
            'total_due': total_due,
            'currency': env.company.currency_id.name,
        })

    @http.route('/api/orca/v1/account/invoices', type='http', auth='none', methods=['POST'], csrf=False)
    def list_invoices(self, **kwargs):
        """Lists invoices matching optional state, limit, partner_id, or ncf."""
        if not self._verify_auth():
            return self._error('Unauthorized: Invalid or missing token', 401)

        try:
            body = json.loads(request.httprequest.data or '{}')
        except Exception:
            body = {}

        domain = [('move_type', 'in', ['out_invoice', 'out_refund'])]
        if body.get('state'):
            domain.append(('state', '=', body['state']))
        if body.get('partner_id'):
            domain.append(('partner_id', '=', int(body['partner_id'])))

        limit = min(int(body.get('limit', 20)), 100)
        records = request.env['account.move'].sudo().search(domain, limit=limit, order='id desc')

        return self._json_response({
            'status': 'success',
            'count': len(records),
            'invoices': [rec.to_orca_dto() for rec in records]
        })

    @http.route('/api/orca/v1/account/invoice/create', type='http', auth='none', methods=['POST'], csrf=False)
    def create_invoice(self, **kwargs):
        """Creates an account.move customer invoice with optional NCF assignment."""
        if not self._verify_auth():
            return self._error('Unauthorized: Invalid or missing token', 401)

        try:
            body = json.loads(request.httprequest.data or '{}')
        except Exception:
            return self._error('Invalid JSON body')

        partner_id = body.get('partner_id')
        if not partner_id:
            return self._error('partner_id is required')

        lines = body.get('lines', [])
        if not lines:
            return self._error('At least one invoice line is required')

        invoice_lines = []
        for l in lines:
            line_vals = {
                'product_id': l.get('product_id'),
                'quantity': l.get('quantity', 1.0),
                'price_unit': l.get('price_unit', 0.0),
                'name': l.get('description') or 'Linea de factura',
            }
            invoice_lines.append((0, 0, line_vals))

        vals = {
            'move_type': 'out_invoice',
            'partner_id': int(partner_id),
            'invoice_date': body.get('invoice_date') or http.fields.Date.today(),
            'invoice_line_ids': invoice_lines,
        }

        try:
            move = request.env['account.move'].sudo().create(vals)
            if body.get('auto_post'):
                move.action_post()
            return self._json_response({
                'status': 'success',
                'invoice': move.to_orca_dto()
            }, status=201)
        except Exception as e:
            _logger.exception("Error creating invoice via ORCA: %s", e)
            return self._error(str(e), 500)

    # ==================== POINT OF SALE (POS) ====================

    @http.route('/api/orca/v1/pos/status', type='http', auth='none', methods=['GET'], csrf=False)
    def pos_status(self, **kwargs):
        """Returns real-time POS configuration and session statuses."""
        if not self._verify_auth():
            return self._error('Unauthorized: Invalid or missing token', 401)

        sessions = request.env['pos.session'].sudo().search([('state', 'in', ['opened', 'opening_control'])])
        configs = request.env['pos.config'].sudo().search([])

        session_list = []
        for s in sessions:
            session_list.append({
                'session_id': s.id,
                'session_name': s.name,
                'config_id': s.config_id.id,
                'config_name': s.config_id.name,
                'user_name': s.user_id.name,
                'state': s.state,
                'start_at': str(s.start_at),
                'total_payments_amount': s.total_payments_amount,
            })

        return self._json_response({
            'status': 'success',
            'active_sessions_count': len(sessions),
            'total_configs_count': len(configs),
            'sessions': session_list
        })

    @http.route('/api/orca/v1/pos/orders', type='http', auth='none', methods=['POST'], csrf=False)
    def list_pos_orders(self, **kwargs):
        """Lists recent POS orders."""
        if not self._verify_auth():
            return self._error('Unauthorized: Invalid or missing token', 401)

        try:
            body = json.loads(request.httprequest.data or '{}')
        except Exception:
            body = {}

        domain = []
        if body.get('session_id'):
            domain.append(('session_id', '=', int(body['session_id'])))
        if body.get('state'):
            domain.append(('state', '=', body['state']))

        limit = min(int(body.get('limit', 20)), 100)
        orders = request.env['pos.order'].sudo().search(domain, limit=limit, order='id desc')

        return self._json_response({
            'status': 'success',
            'count': len(orders),
            'orders': [o.to_orca_dto() for o in orders]
        })

    # ==================== STOCK / INVENTORY ====================

    @http.route('/api/orca/v1/stock/levels', type='http', auth='none', methods=['POST'], csrf=False)
    def stock_levels(self, **kwargs):
        """Checks stock availability and inventory levels for products."""
        if not self._verify_auth():
            return self._error('Unauthorized: Invalid or missing token', 401)

        try:
            body = json.loads(request.httprequest.data or '{}')
        except Exception:
            body = {}

        domain = [('type', 'in', ['consu', 'product'])]
        if body.get('product_id'):
            domain.append(('id', '=', int(body['product_id'])))
        if body.get('barcode'):
            domain.append(('barcode', '=', str(body['barcode'])))
        if body.get('query'):
            domain.append(('name', 'ilike', str(body['query'])))

        limit = min(int(body.get('limit', 30)), 100)
        products = request.env['product.product'].sudo().search(domain, limit=limit)

        return self._json_response({
            'status': 'success',
            'count': len(products),
            'items': [p.to_orca_stock_dto() for p in products]
        })

    # ==================== KITCHEN / PREPARATION ====================

    @http.route('/api/orca/v1/kitchen/orders', type='http', auth='none', methods=['GET', 'POST'], csrf=False)
    def kitchen_orders(self, **kwargs):
        """Returns live kitchen preparation orders if pos_kitchen_core is installed."""
        if not self._verify_auth():
            return self._error('Unauthorized: Invalid or missing token', 401)

        env = request.env
        if 'pos.preparation' in env:
            preps = env['pos.preparation'].sudo().search([], limit=50, order='id desc')
            items = []
            for p in preps:
                items.append({
                    'id': p.id,
                    'name': p.name if hasattr(p, 'name') else f'Prep #{p.id}',
                    'state': getattr(p, 'state', 'pending'),
                    'order_id': p.order_id.id if hasattr(p, 'order_id') and p.order_id else None,
                    'order_ref': p.order_id.pos_reference if hasattr(p, 'order_id') and p.order_id else '',
                })
            return self._json_response({'status': 'success', 'kitchen_module': 'pos.preparation', 'items': items})
        else:
            # Fallback to pos.order lines for food items
            orders = env['pos.order'].sudo().search([('state', '=', 'draft')], limit=20, order='id desc')
            items = []
            for o in orders:
                for line in o.lines:
                    items.append({
                        'order_id': o.id,
                        'order_ref': o.pos_reference or o.name,
                        'product_id': line.product_id.id,
                        'product_name': line.product_id.name,
                        'qty': line.qty,
                        'state': 'pending',
                    })
            return self._json_response({'status': 'success', 'kitchen_module': 'pos.order.lines', 'items': items})
