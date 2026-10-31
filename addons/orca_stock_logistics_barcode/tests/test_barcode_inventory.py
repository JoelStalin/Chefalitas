from unittest.mock import patch

from odoo.tests.common import TransactionCase


class TestOrcaStockLogisticsBarcode(TransactionCase):
    """ORCA Stock Logistics Barcode on Odoo 20: packaging barcodes live in product.uom (product + packaging unit)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Product = cls.env["product.product"]
        cls.Enrichment = cls.env["orca.barcode.enrichment.cache"]
        cls.Inventory = cls.env["stock.inventory"]

        cls.product_cola = cls.Product.create(
            {"name": "Refresco Cola 355ml", "default_code": "COLA-355", "barcode": "7460001112228", "type": "consu"}
        )
        cls.box_24 = cls.env["uom.uom"].create(
            {"name": "Caja x24 (prueba)", "relative_uom_id": cls.product_cola.uom_id.id, "relative_factor": 24.0}
        )
        cls.pack_box_24 = cls.env["product.uom"].create(
            {
                "product_id": cls.product_cola.id,
                "uom_id": cls.box_24.id,
                "barcode": "17460001112225",
                "package_level_type": "master_box",
            }
        )

    def test_01_unit_vs_packaging_barcode_resolution(self):
        """Unit barcode resolves with factor 1; the box barcode resolves with the factor of its packaging unit (24)."""
        unit_res = self.Product.resolve_barcode_fast("7460001112228")
        self.assertTrue(unit_res["found"])
        self.assertEqual(unit_res["match_type"], "product")
        self.assertEqual(unit_res["qty_per_box"], 1.0)
        self.assertEqual(unit_res["product_id"], self.product_cola.id)

        box_res = self.Product.resolve_barcode_fast("17460001112225")
        self.assertTrue(box_res["found"])
        self.assertEqual(box_res["match_type"], "packaging")
        self.assertEqual(box_res["qty_per_box"], 24.0)
        self.assertEqual(box_res["product_id"], self.product_cola.id)
        self.assertEqual(box_res["packaging_id"], self.pack_box_24.id)
        self.assertEqual(box_res["packaging_name"], "Caja x24 (prueba)")
        self.assertEqual(self.pack_box_24.effective_unit_factor, 24.0)

        self.assertFalse(self.Product.resolve_barcode_fast("0000000000000")["found"])

    def test_02_inventory_session_multiplies_master_box_qty(self):
        """2 master boxes (24 units each) + 3 single units = 51 units on one line."""
        stock_loc = self.env.ref("stock.stock_location_stock")
        inv = self.Inventory.create({"name": "Conteo Cíclico Almacén Central", "location_id": stock_loc.id})
        res = inv.action_process_barcode_batch(
            [
                {"barcode": "17460001112225", "count": 2.0},  # 2 boxes * 24 = 48
                {"barcode": "7460001112228", "count": 3.0},   # 3 units * 1 = 3
            ],
            auto_enrich=False,
        )
        self.assertEqual(res["processed_count"], 2)
        line = inv.line_ids.filtered(lambda l: l.product_id == self.product_cola)
        self.assertEqual(len(line), 1)
        self.assertEqual(line.product_qty, 51.0)

    def test_03_warmup_catalog_includes_packaging_barcodes(self):
        entries = {e["barcode"]: e for e in self.Product.warmup_barcode_catalog(limit=1000)["entries"]}
        self.assertEqual(entries["7460001112228"]["match_type"], "product")
        self.assertEqual(entries["17460001112225"]["match_type"], "packaging")
        self.assertEqual(entries["17460001112225"]["qty_per_box"], 24.0)

    def test_04_typology_detection(self):
        itf = self.Enrichment.detect_barcode_typology("17460001112225")
        self.assertEqual(itf["barcode_standard"], "itf14")
        self.assertTrue(itf["is_master_pack_barcode"])

        weight = self.Enrichment.detect_barcode_typology("2112345012504")
        self.assertEqual(weight["barcode_standard"], "gs1_weight")
        self.assertAlmostEqual(weight["embedded_weight_kg"], 1.250, places=3)

    def test_05_create_master_box_on_the_fly_makes_a_product_uom(self):
        """An unknown ITF-14 box creates the unit product, a packaging unit "Caja x12" and its product.uom barcode."""
        enriched = {"found": True, "name": "Café Molido 454 g", "brand": "Induban", "weight": 0.454,
                    "is_master_pack_barcode": True, "inferred_qty_per_box": 12.0, "source_api": "openfoodfacts"}
        with patch.object(type(self.Enrichment), "fetch_external_product_metadata", return_value=enriched):
            res = self.Enrichment.action_create_product_from_enrichment("17460123456786", qty_per_box=12.0)
        self.assertTrue(res["found"])
        self.assertEqual(res["match_type"], "packaging")
        self.assertEqual(res["qty_per_box"], 12.0)
        pkg = self.env["product.uom"].search([("barcode", "=", "17460123456786")])
        self.assertEqual(pkg.uom_id.relative_factor, 12.0)
        self.assertEqual(pkg.product_id.orca_brand_name, "Induban")
