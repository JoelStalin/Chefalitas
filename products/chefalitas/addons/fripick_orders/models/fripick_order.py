from odoo import fields, models


class FripickOrder(models.Model):
    """A closed POS order captured for its company: kitchen preparation data and the monthly invoice link."""
    _name = "fripick.order"
    _description = "Fripick order"
    _order = "closed_at desc, id desc"

    name = fields.Char(required=True)
    company_id = fields.Many2one("res.company", required=True, index=True)
    pos_order_id = fields.Many2one("pos.order", ondelete="set null", index=True)
    closed_at = fields.Datetime(required=True, index=True)
    line_ids = fields.One2many("fripick.order.line", "order_id")
    amount_total = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one(related="company_id.currency_id")
    invoice_id = fields.Many2one("account.move", readonly=True, copy=False, index=True)

    _pos_order_unique = models.Constraint("unique(pos_order_id)", "Este pedido ya fue capturado.")


class FripickOrderLine(models.Model):
    _name = "fripick.order.line"
    _description = "Fripick order line"

    order_id = fields.Many2one("fripick.order", required=True, ondelete="cascade")
    product_id = fields.Many2one("product.product")
    name = fields.Char(required=True)
    qty = fields.Float(default=1.0)
    preparation = fields.Char(help="Kitchen notes: customer note and selected attributes.")
