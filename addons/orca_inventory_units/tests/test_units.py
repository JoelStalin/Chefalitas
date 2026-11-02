from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "orca_units")
class TestOrcaUnits(TransactionCase):
    def test_sold_by_pound_sets_pound_to_weigh_and_pos(self):
        p = self.env["product.template"].create({"name": "Pollo entero", "orca_sold_by_pound": True, "list_price": 85.0})
        self.assertEqual(p.uom_id, self.env.ref("uom.product_uom_lb"))
        self.assertTrue(p.uom_id.active)
        self.assertTrue(p.to_weight)
        self.assertTrue(p.available_in_pos)
        self.assertEqual(p.list_price, 85.0, "the sale price is the price per pound")

    def test_uncheck_pound_goes_back_to_units(self):
        p = self.env["product.template"].create({"name": "Queso", "orca_sold_by_pound": True})
        p.orca_sold_by_pound = False
        self.assertEqual(p.uom_id, self.env.ref("uom.product_uom_unit"))
        self.assertFalse(p.to_weight)

    def test_box_creates_unit_pos_barcode_and_stays_sold_by_unit(self):
        p = self.env["product.template"].create(
            {"name": "Refresco 355", "orca_units_per_box": 24, "orca_box_barcode": "17460001112225"}
        )
        self.assertEqual(p.uom_id, self.env.ref("uom.product_uom_unit"), "sold by unit")
        box = p.uom_ids.filtered(lambda u: u.name == "Caja x24")
        self.assertEqual(len(box), 1)
        self.assertEqual(box.relative_factor, 24)
        line = self.env["product.uom"].search([("product_id", "=", p.product_variant_id.id), ("uom_id", "=", box.id)])
        self.assertEqual(line.barcode, "17460001112225")

    def test_same_box_size_reuses_the_unit(self):
        a = self.env["product.template"].create({"name": "A", "orca_units_per_box": 12})
        b = self.env["product.template"].create({"name": "B", "orca_units_per_box": 12})
        self.assertEqual(a.uom_ids & b.uom_ids, a.uom_ids.filtered(lambda u: u.name == "Caja x12"))

    def test_units_per_box_must_be_more_than_one(self):
        with self.assertRaises(ValidationError):
            self.env["product.template"].create({"name": "Mal", "orca_units_per_box": 1})
