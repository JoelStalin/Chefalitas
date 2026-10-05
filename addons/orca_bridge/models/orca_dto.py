# -*- coding: utf-8 -*-
import logging
from odoo import models, api

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    def to_orca_dto(self):
        """Converts an account.move record to an ORCA standardized DTO dictionary."""
        self.ensure_one()
        
        # NCF extraction for Dominican Republic localization if available
        ncf = None
        if hasattr(self, 'l10n_do_fiscal_number') and self.l10n_do_fiscal_number:
            ncf = self.l10n_do_fiscal_number
        elif hasattr(self, 'l10n_latam_document_number') and self.l10n_latam_document_number:
            ncf = self.l10n_latam_document_number

        lines = []
        for line in self.invoice_line_ids:
            lines.append({
                'id': line.id,
                'product_id': line.product_id.id if line.product_id else None,
                'product_name': line.product_id.name if line.product_id else line.name,
                'quantity': line.quantity,
                'price_unit': line.price_unit,
                'price_subtotal': line.price_subtotal,
                'price_total': line.price_total,
            })

        return {
            'id': self.id,
            'name': self.name,
            'ref': self.ref or '',
            'state': self.state,
            'move_type': self.move_type,
            'invoice_date': str(self.invoice_date) if self.invoice_date else None,
            'currency': self.currency_id.name if self.currency_id else 'DOP',
            'amount_untaxed': self.amount_untaxed,
            'amount_tax': self.amount_tax,
            'amount_total': self.amount_total,
            'amount_residual': self.amount_residual,
            'partner': {
                'id': self.partner_id.id if self.partner_id else None,
                'name': self.partner_id.name if self.partner_id else None,
                'vat': self.partner_id.vat if self.partner_id else None,
            },
            'ncf': ncf,
            'lines': lines,
        }


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def to_orca_dto(self):
        """Converts a pos.order record to an ORCA standardized DTO dictionary."""
        self.ensure_one()
        lines = []
        for l in self.lines:
            lines.append({
                'id': l.id,
                'product_id': l.product_id.id,
                'product_name': l.product_id.name,
                'qty': l.qty,
                'price_unit': l.price_unit,
                'price_subtotal': l.price_subtotal,
                'price_subtotal_incl': l.price_subtotal_incl,
                'discount': l.discount,
            })

        payments = []
        for p in self.payment_ids:
            payments.append({
                'id': p.id,
                'payment_method': p.payment_method_id.name if p.payment_method_id else 'Desconocido',
                'amount': p.amount,
                'payment_date': str(p.payment_date) if p.payment_date else None,
            })

        return {
            'id': self.id,
            'name': self.name,
            'pos_reference': self.pos_reference,
            'session_id': self.session_id.id,
            'session_name': self.session_id.name,
            'state': self.state,
            'date_order': str(self.date_order) if self.date_order else None,
            'partner': {
                'id': self.partner_id.id if self.partner_id else None,
                'name': self.partner_id.name if self.partner_id else None,
            },
            'amount_total': self.amount_total,
            'amount_tax': self.amount_tax,
            'amount_paid': self.amount_paid,
            'amount_return': self.amount_return,
            'lines': lines,
            'payments': payments,
        }


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def to_orca_stock_dto(self):
        """Returns stock balance and inventory details for ORCA."""
        self.ensure_one()
        return {
            'product_id': self.id,
            'default_code': self.default_code or '',
            'barcode': self.barcode or '',
            'name': self.name,
            'uom': self.uom_id.name if self.uom_id else 'Unidades',
            'list_price': self.list_price,
            'standard_price': self.standard_price,
            'qty_available': self.qty_available,
            'virtual_available': self.virtual_available,
            'incoming_qty': self.incoming_qty,
            'outgoing_qty': self.outgoing_qty,
        }
