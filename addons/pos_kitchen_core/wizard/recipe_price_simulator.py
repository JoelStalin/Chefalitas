from odoo import api, fields, models


class RecipePriceSimulator(models.TransientModel):
    _name = "recipe.price.simulator"
    _description = "Recipe Price Simulator"

    recipe_id = fields.Many2one("rest.recipe", required=True)
    target_margin_pct = fields.Float(string="Target Margin %")
    sale_price = fields.Monetary(string="Sale Price")
    currency_id = fields.Many2one("res.currency", related="recipe_id.currency_id")

    resulting_margin_pct = fields.Float(compute="_compute_results")
    suggested_price = fields.Monetary(compute="_compute_results")
    impact_note = fields.Text(compute="_compute_results")

    @api.depends("target_margin_pct", "sale_price", "recipe_id.theoretical_cost_per_portion")
    def _compute_results(self):
        for wizard in self:
            cost = wizard.recipe_id.theoretical_cost_per_portion
            if wizard.sale_price:
                sale_price = wizard.sale_price
            else:
                margin = wizard.target_margin_pct or wizard.recipe_id.target_margin_pct
                sale_price = cost / (1 - margin / 100) if margin < 100 else 0.0
            wizard.suggested_price = sale_price
            wizard.resulting_margin_pct = (
                ((sale_price - cost) / sale_price) * 100 if sale_price else 0.0
            )
            wizard.impact_note = (
                "Suggested price based on current recipe cost." if sale_price else ""
            )
