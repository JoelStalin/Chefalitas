from odoo import api, fields, models
from odoo.exceptions import ValidationError


class RestPreparation(models.Model):
    _name = "rest.preparation"
    _description = "Kitchen Preparation"
    _order = "date desc"

    name = fields.Char(required=True, copy=False, default="/")
    recipe_id = fields.Many2one("rest.recipe", required=True)
    date = fields.Datetime(default=fields.Datetime.now)
    prepared_portions = fields.Float(default=0.0)
    real_total_weight_g = fields.Float(string="Real Total Weight (g)")
    expected_total_weight_g = fields.Float(related="recipe_id.expected_total_weight_g", store=True)
    variance_pct = fields.Float(compute="_compute_variance", store=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("in_progress", "In Progress"),
            ("prepared", "Prepared"),
            ("closed", "Closed"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
    )
    user_id = fields.Many2one("res.users", default=lambda self: self.env.user)
    line_consumption_ids = fields.One2many("rest.preparation.line", "preparation_id")
    leftover_ids = fields.One2many("rest.leftover", "preparation_id")
    waste_ids = fields.One2many("rest.waste", "preparation_id")
    real_total_cost = fields.Monetary(compute="_compute_real_costs", store=True)
    real_cost_per_portion = fields.Monetary(compute="_compute_real_costs", store=True)
    currency_id = fields.Many2one("res.currency", related="recipe_id.currency_id")

    @api.model
    def create(self, vals):
        if vals.get("name", "/") == "/":
            vals["name"] = self.env["ir.sequence"].next_by_code("rest.preparation") or "/"
        return super().create(vals)

    @api.depends("real_total_weight_g", "expected_total_weight_g")
    def _compute_variance(self):
        for preparation in self:
            if preparation.expected_total_weight_g:
                preparation.variance_pct = (
                    (preparation.real_total_weight_g - preparation.expected_total_weight_g)
                    / preparation.expected_total_weight_g
                    * 100
                )
            else:
                preparation.variance_pct = 0.0

    @api.depends("line_consumption_ids.cost_value", "prepared_portions")
    def _compute_real_costs(self):
        for preparation in self:
            total_cost = sum(preparation.line_consumption_ids.mapped("cost_value"))
            preparation.real_total_cost = total_cost
            preparation.real_cost_per_portion = (
                total_cost / preparation.prepared_portions if preparation.prepared_portions else 0.0
            )

    @api.constrains("prepared_portions")
    def _check_prepared_portions(self):
        for preparation in self:
            if preparation.prepared_portions < 0:
                raise ValidationError("Prepared portions cannot be negative.")


class RestPreparationLine(models.Model):
    _name = "rest.preparation.line"
    _description = "Preparation Consumption Line"

    preparation_id = fields.Many2one("rest.preparation", ondelete="cascade", required=True)
    ingredient_id = fields.Many2one("product.product", required=True)
    qty_g = fields.Float(string="Quantity (g)", required=True)
    cost_value = fields.Monetary(compute="_compute_cost", store=True)
    currency_id = fields.Many2one("res.currency", related="preparation_id.currency_id")

    @api.depends("qty_g", "ingredient_id")
    def _compute_cost(self):
        for line in self:
            cost_per_g = line.ingredient_id.x_cost_per_base_uom if line.ingredient_id else 0.0
            line.cost_value = line.qty_g * cost_per_g
