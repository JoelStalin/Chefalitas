from odoo import api, fields, models
from odoo.exceptions import ValidationError


class RestRecipe(models.Model):
    _name = "rest.recipe"
    _description = "Kitchen Recipe"
    _order = "name"

    name = fields.Char(required=True)
    product_id = fields.Many2one("product.product", required=True)
    line_ids = fields.One2many("rest.recipe.line", "recipe_id")
    expected_portions = fields.Float(default=1.0, required=True)
    standard_portion_weight_g = fields.Float(string="Standard Portion Weight (g)", default=0.0)
    expected_total_weight_g = fields.Float(compute="_compute_expected_total_weight", store=True)
    theoretical_total_cost = fields.Monetary(compute="_compute_costs", store=True)
    theoretical_cost_per_portion = fields.Monetary(compute="_compute_costs", store=True)
    target_margin_pct = fields.Float(default=30.0)
    suggested_sale_price = fields.Monetary(compute="_compute_suggested_price", store=True)
    currency_id = fields.Many2one("res.currency", related="company_id.currency_id")
    active = fields.Boolean(default=True)
    notes_kitchen = fields.Text()
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    @api.depends("expected_portions", "standard_portion_weight_g")
    def _compute_expected_total_weight(self):
        for recipe in self:
            recipe.expected_total_weight_g = (
                recipe.expected_portions * recipe.standard_portion_weight_g
            )

    @api.depends("line_ids.qty_g", "line_ids.ingredient_id", "line_ids.uom_id")
    def _compute_costs(self):
        for recipe in self:
            total_cost = 0.0
            for line in recipe.line_ids:
                ingredient = line.ingredient_id
                if not ingredient:
                    continue
                qty_g = line.qty_g
                cost_per_g = ingredient.x_cost_per_base_uom or 0.0
                yield_factor = ingredient.x_yield_factor or 1.0
                total_cost += (qty_g * cost_per_g) / yield_factor
            recipe.theoretical_total_cost = total_cost
            recipe.theoretical_cost_per_portion = (
                total_cost / recipe.expected_portions if recipe.expected_portions else 0.0
            )

    @api.depends("theoretical_cost_per_portion", "target_margin_pct")
    def _compute_suggested_price(self):
        for recipe in self:
            if recipe.target_margin_pct >= 100:
                recipe.suggested_sale_price = 0.0
            else:
                recipe.suggested_sale_price = recipe.theoretical_cost_per_portion / (
                    1 - recipe.target_margin_pct / 100
                )

    @api.constrains("expected_portions")
    def _check_expected_portions(self):
        for recipe in self:
            if recipe.expected_portions <= 0:
                raise ValidationError("Expected portions must be greater than zero.")

    @api.constrains("product_id")
    def _check_product_saleable(self):
        for recipe in self:
            if recipe.product_id and not recipe.product_id.sale_ok:
                raise ValidationError("Recipe product must be saleable.")

    @api.constrains("line_ids")
    def _check_lines(self):
        for recipe in self:
            if not recipe.line_ids:
                raise ValidationError("Recipe must have at least one ingredient line.")
