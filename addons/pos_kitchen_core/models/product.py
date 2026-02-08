from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    x_is_ingredient = fields.Boolean(string="Is Ingredient")
    x_yield_factor = fields.Float(string="Yield Factor", default=1.0)
    x_cost_per_base_uom = fields.Monetary(
        string="Cost per Base UoM", compute="_compute_cost_per_base_uom", store=True
    )
    x_last_cost_update = fields.Datetime(string="Last Cost Update")
    x_cost_variation_pct = fields.Float(
        string="Cost Variation %", compute="_compute_cost_variation_pct", store=True
    )
    x_cost_alert_threshold_pct = fields.Float(string="Cost Alert Threshold %", default=15)

    @api.depends("standard_price", "uom_id", "x_yield_factor")
    def _compute_cost_per_base_uom(self):
        for product in self:
            if not product.uom_id:
                product.x_cost_per_base_uom = 0.0
                continue
            qty_in_base = product.uom_id._compute_quantity(1, product.uom_id)
            yield_factor = product.x_yield_factor or 1.0
            product.x_cost_per_base_uom = (product.standard_price / qty_in_base) / yield_factor

    @api.depends("standard_price", "x_last_cost_update")
    def _compute_cost_variation_pct(self):
        for product in self:
            product.x_cost_variation_pct = 0.0

    @api.constrains("x_is_ingredient", "type")
    def _check_ingredient_type(self):
        for product in self:
            if product.x_is_ingredient and product.type not in ("product", "consu"):
                raise ValidationError("Ingredients must be storable or consumable products.")

    @api.constrains("uom_id")
    def _check_uom_category(self):
        for product in self:
            if product.x_is_ingredient and not product.uom_id:
                raise ValidationError("Ingredient must have a unit of measure.")


class ProductProduct(models.Model):
    _inherit = "product.product"

    x_is_ingredient = fields.Boolean(related="product_tmpl_id.x_is_ingredient", store=True)
    x_yield_factor = fields.Float(related="product_tmpl_id.x_yield_factor", store=True)
    x_cost_per_base_uom = fields.Monetary(
        related="product_tmpl_id.x_cost_per_base_uom", store=True
    )
    x_last_cost_update = fields.Datetime(related="product_tmpl_id.x_last_cost_update")
    x_cost_variation_pct = fields.Float(related="product_tmpl_id.x_cost_variation_pct")
    x_cost_alert_threshold_pct = fields.Float(
        related="product_tmpl_id.x_cost_alert_threshold_pct"
    )
