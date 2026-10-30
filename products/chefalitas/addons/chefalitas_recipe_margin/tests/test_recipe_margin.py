from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestRecipeMargin(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.wh = cls.env["stock.warehouse"].search([("company_id", "=", cls.env.company.id)], limit=1)
        cls.stock = cls.wh.lot_stock_id
        cls.customers = cls.env.ref("stock.stock_location_customers")
        cls.supplier = cls.env.ref("stock.stock_location_suppliers")
        cls.categ = cls.env["product.category"].create({"name": "Alitas", "target_margin": 65})
        lb = cls.env.ref("uom.product_uom_lb")
        cls.chicken = cls.env["product.product"].create({
            "name": "Alas de pollo", "is_storable": True, "uom_id": lb.id, "standard_price": 50.0})
        cls.sauce = cls.env["product.product"].create({
            "name": "Salsa bbq", "is_storable": True, "standard_price": 100.0})
        cls.dish = cls.env["product.product"].create({
            "name": "Alitas x8", "type": "consu", "list_price": 300.0, "categ_id": cls.categ.id, "sale_ok": True})
        cls.bom = cls.env["mrp.bom"].create({
            "product_tmpl_id": cls.dish.product_tmpl_id.id, "type": "phantom", "product_qty": 1,
            "bom_line_ids": [(0, 0, {"product_id": cls.chicken.id, "product_qty": 1.0, "uom_id": lb.id}),
                             (0, 0, {"product_id": cls.sauce.id, "product_qty": 0.1})]})

    def _move(self, product, qty, src, dst, inventory=False):
        move = self.env["stock.move"].create({
            "product_id": product.id, "product_uom_qty": qty, "uom_id": product.uom_id.id,
            "location_id": src.id, "location_dest_id": dst.id, "is_inventory": inventory})
        move._action_confirm()
        move.quantity = qty
        move.picked = True
        move._action_done()
        return move

    def _sell(self, qty):
        out = self.env["stock.picking"].create({
            "picking_type_id": self.wh.out_type_id.id, "location_id": self.stock.id,
            "location_dest_id": self.customers.id,
            "move_ids": [(0, 0, {"product_id": self.dish.id, "product_uom_qty": qty, "uom_id": self.dish.uom_id.id,
                                 "location_id": self.stock.id, "location_dest_id": self.customers.id})]})
        out.action_confirm()  # the kit explodes into ingredient moves here
        for move in out.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        out._action_done()
        return out

    def test_cost_margin_and_no_suggestion_when_margin_is_fine(self):
        tmpl = self.dish.product_tmpl_id
        self.assertEqual(tmpl.recipe_bom_id, self.bom)
        self.assertAlmostEqual(tmpl.recipe_cost, 60.0)  # 1 lb x 50 + 0.1 x 100
        self.assertAlmostEqual(tmpl.recipe_margin, 80.0)
        self.assertFalse(tmpl.suggested_price)

    def test_ingredient_cost_rise_suggests_a_rounded_price(self):
        self.chicken.standard_price = 120.0  # new supplier invoice
        tmpl = self.dish.product_tmpl_id
        self.assertAlmostEqual(tmpl.recipe_cost, 130.0)
        self.assertAlmostEqual(tmpl.recipe_margin, 56.67, places=2)
        self.assertEqual(tmpl.suggested_price, 375.0)  # 130 / 0.35 = 371.43 -> next multiple of 5
        suggestions = self.env["product.template"]._price_suggestions()
        self.assertIn(375.0, [s["suggested_price"] for s in suggestions if s["product"] == "Alitas x8"])

    def test_selling_a_dish_consumes_its_ingredients(self):
        self._move(self.chicken, 10, self.supplier, self.stock)
        self._move(self.sauce, 2, self.supplier, self.stock)
        self._sell(4)
        self.assertAlmostEqual(self.chicken.qty_available, 6.0)
        self.assertAlmostEqual(self.sauce.qty_available, 1.6)

    def test_waste_check_flags_the_ingredient_whose_recipe_is_off(self):
        loss = self.env["stock.location"].search([("usage", "=", "inventory")], limit=1)
        self._move(self.chicken, 10, self.supplier, self.stock)
        self._move(self.sauce, 2, self.supplier, self.stock)
        self._sell(5)                                                  # theoretical: 5 lb chicken, 0.5 sauce
        self._move(self.chicken, 2, self.stock, loss, inventory=True)  # the count found 2 lb less than expected
        wizard = self.env["recipe.variance.wizard"].create({
            "date_from": fields.Datetime.subtract(fields.Datetime.now(), days=1),
            "date_to": fields.Datetime.add(fields.Datetime.now(), days=1)})
        wizard.action_compute()
        by_product = {l.product_id: l for l in wizard.line_ids}
        chicken, sauce = by_product[self.chicken], by_product[self.sauce]
        self.assertEqual((chicken.purchased, chicken.consumed, chicken.waste), (10, 5, 2))
        self.assertAlmostEqual(chicken.waste_pct, 40.0)
        self.assertTrue(chicken.flagged)
        self.assertAlmostEqual(sauce.consumed, 0.5)
        self.assertFalse(sauce.flagged)
