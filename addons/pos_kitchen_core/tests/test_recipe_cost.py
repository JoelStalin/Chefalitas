from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestRecipeCost(TransactionCase):

    def test_recipe_cost_uses_grams_and_yield_once(self):
        kg = self.env.ref("uom.product_uom_kgm")
        chicken = self.env["product.product"].create({
            "name": "Pollo", "type": "consu", "uom_id": kg.id,
            "standard_price": 200.0,  # RD$ 200 / kg
            "x_is_ingredient": True,
        })
        # x_yield_factor is edited on the template (related + readonly on the variant)
        chicken.product_tmpl_id.x_yield_factor = 0.8  # 20% merma al limpiar
        self.assertAlmostEqual(chicken.x_cost_per_base_uom, 0.2)  # RD$ 0.20 / g
        dish = self.env["product.product"].create({"name": "Pollo al horno", "sale_ok": True})
        recipe = self.env["rest.recipe"].create({
            "name": "Pollo al horno", "product_id": dish.id, "expected_portions": 2,
            "target_margin_pct": 30.0,
            "line_ids": [(0, 0, {"ingredient_id": chicken.id, "uom_id": self.env.ref("uom.product_uom_gram").id,
                                 "qty_g": 500.0})],
        })
        # 500 g x 0.20 = 100.00 bruto; con rendimiento 0.8 -> 125.00; 2 porciones -> 62.50
        self.assertAlmostEqual(recipe.theoretical_total_cost, 125.0)
        self.assertAlmostEqual(recipe.theoretical_cost_per_portion, 62.5)
        self.assertAlmostEqual(recipe.suggested_sale_price, 62.5 / 0.7, places=2)
