from odoo import api, fields, models
from odoo.exceptions import ValidationError


class RestRecipeLine(models.Model):
    _name = "rest.recipe.line"
    _description = "Recipe Line"

    recipe_id = fields.Many2one("rest.recipe", required=True, ondelete="cascade")
    ingredient_id = fields.Many2one(
        "product.product", required=True, domain=[("x_is_ingredient", "=", True)]
    )
    qty_g = fields.Float(string="Quantity (g)", required=True)
    uom_id = fields.Many2one("uom.uom", required=True)

    @api.onchange("uom_id")
    def _onchange_uom_id(self):
        gram_uom = self.env.ref("uom.product_uom_gram", raise_if_not_found=False)
        # Odoo 20 has no UoM categories: convert only between units sharing a reference (g, kg...)
        if self.uom_id and gram_uom and self.uom_id._has_common_reference(gram_uom):
            self.qty_g = self.uom_id._compute_quantity(self.qty_g, gram_uom)

    @api.constrains("qty_g")
    def _check_qty(self):
        for line in self:
            if line.qty_g <= 0:
                raise ValidationError("Quantity must be greater than zero.")
