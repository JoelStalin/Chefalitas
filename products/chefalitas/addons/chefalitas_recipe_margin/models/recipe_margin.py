"""Recipes (kit BoMs), cost per dish, margin vs. target, price suggestions and the waste check
(docs/SPEC_compras_whatsapp.md, stages 3 and 4)."""
import math

from odoo import _, api, fields, models

DEFAULT_TARGET_MARGIN = 65.0  # % of the sale price
PRICE_STEP = 5.0              # menu prices end in 0 or 5 (RD$)


class ProductCategory(models.Model):
    _inherit = "product.category"

    target_margin = fields.Float("Margen objetivo (%)", default=DEFAULT_TARGET_MARGIN,
                                 help="Gross margin the dishes of this category should keep: (price - cost) / price.")


class ProductTemplate(models.Model):
    _inherit = "product.template"

    recipe_bom_id = fields.Many2one("mrp.bom", compute="_compute_recipe", string="Receta")
    recipe_cost = fields.Float("Costo de receta", compute="_compute_recipe", digits="Product Price",
                               help="Sum of ingredient quantity x ingredient cost, for one unit of the dish.")
    recipe_margin = fields.Float("Margen (%)", compute="_compute_recipe")
    target_margin = fields.Float(related="categ_id.target_margin")
    suggested_price = fields.Float("Precio sugerido", compute="_compute_recipe", digits="Product Price")

    @api.depends("list_price", "categ_id.target_margin", "bom_ids.type", "bom_ids.bom_line_ids.product_qty",
                 "bom_ids.bom_line_ids.product_id.standard_price")
    def _compute_recipe(self):
        for tmpl in self:
            bom = self.env["mrp.bom"]._bom_find(tmpl.product_variant_id, bom_type="phantom").get(tmpl.product_variant_id) \
                if tmpl.product_variant_id else self.env["mrp.bom"]
            tmpl.recipe_bom_id = bom
            cost = bom._recipe_unit_cost() if bom else 0.0
            tmpl.recipe_cost = cost
            tmpl.recipe_margin = (tmpl.list_price - cost) / tmpl.list_price * 100 if tmpl.list_price else 0.0
            target = (tmpl.categ_id.target_margin or DEFAULT_TARGET_MARGIN) / 100
            needed = cost / (1 - target) if bom and target < 1 else 0.0
            tmpl.suggested_price = math.ceil(needed / PRICE_STEP) * PRICE_STEP if needed > tmpl.list_price else 0.0

    @api.model
    def _price_suggestions(self):
        """Dishes whose recipe cost pushes the margin under the category target. ORCA sends these to the manager;
        prices are never changed automatically."""
        dishes = self.search([("bom_ids.type", "=", "phantom"), ("sale_ok", "=", True)])
        return [{
            "product": d.display_name, "price": d.list_price, "cost": round(d.recipe_cost, 2),
            "margin": round(d.recipe_margin, 1), "target": d.target_margin, "suggested_price": d.suggested_price,
        } for d in dishes if d.suggested_price]


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    def _recipe_unit_cost(self):
        self.ensure_one()
        total = sum(line.product_id.standard_price * line.uom_id._compute_quantity(
            line.product_qty, line.product_id.uom_id) for line in self.bom_line_ids)
        return total / (self.product_qty or 1.0)


class RecipeVarianceWizard(models.TransientModel):
    """ORCA's own test of the recipes: for each ingredient over a period,
        theoretical consumption = what the sold dishes consumed through their kits,
        waste = stock lost in inventory counts.
    A waste that is large compared to the consumption means the recipe uses more (or less) than it says."""

    _name = "recipe.variance.wizard"
    _description = "Merma por insumo"

    date_from = fields.Datetime(required=True, default=lambda self: fields.Datetime.subtract(fields.Datetime.now(), days=30))
    date_to = fields.Datetime(required=True, default=fields.Datetime.now)
    tolerance = fields.Float("Tolerancia (%)", default=10.0)
    line_ids = fields.One2many("recipe.variance.line", "wizard_id", readonly=True)

    def action_compute(self):
        self.ensure_one()
        self.line_ids.unlink()
        moves = self.env["stock.move"].search([
            ("state", "=", "done"), ("date", ">=", self.date_from), ("date", "<=", self.date_to),
            ("product_id.is_storable", "=", True)])
        data = {}
        for move in moves:
            entry = data.setdefault(move.product_id, {"purchased": 0.0, "consumed": 0.0, "waste": 0.0})
            qty = move.uom_id._compute_quantity(move.quantity, move.product_id.uom_id)
            src, dst = move.location_id.usage, move.location_dest_id.usage
            if src == "supplier" and dst == "internal":
                entry["purchased"] += qty
            elif src == "internal" and dst == "customer" and move.bom_line_id:
                entry["consumed"] += qty  # component of a sold dish (kit)
            elif move.is_inventory:
                entry["waste"] += qty if src == "internal" else -qty
        lines = []
        for product, e in data.items():
            if not e["consumed"] and not e["waste"]:
                continue
            ratio = e["waste"] / e["consumed"] * 100 if e["consumed"] else 100.0
            lines.append((0, 0, {
                "product_id": product.id, "purchased": e["purchased"], "consumed": e["consumed"], "waste": e["waste"],
                "waste_pct": ratio, "flagged": abs(ratio) > self.tolerance,
            }))
        self.line_ids = lines
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id, "view_mode": "form", "target": "new"}


class RecipeVarianceLine(models.TransientModel):
    _name = "recipe.variance.line"
    _description = "Merma de un insumo"
    _order = "flagged desc, waste_pct desc"

    wizard_id = fields.Many2one("recipe.variance.wizard", ondelete="cascade")
    product_id = fields.Many2one("product.product", "Insumo")
    purchased = fields.Float("Comprado")
    consumed = fields.Float("Consumo teórico", help="Consumed by the dishes sold, according to their recipes")
    waste = fields.Float("Merma", help="Lost in inventory counts (positive = less stock than expected)")
    waste_pct = fields.Float("Merma / consumo (%)")
    flagged = fields.Boolean("Revisar receta")
