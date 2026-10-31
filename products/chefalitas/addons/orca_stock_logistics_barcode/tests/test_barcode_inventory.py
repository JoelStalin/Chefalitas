from unittest.mock import patch

from odoo.tests.common import TransactionCase


class TestOrcaStockLogisticsBarcode(TransactionCase):
    """Test suite for Odoo 20 ORCA Stock Logistics Barcode (OCA v19 -> v20)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Product = cls.env["product.product"]
        cls.Packaging = cls.env["product.packaging"]
        cls.Enrichment = cls.env["orca.barcode.enrichment.cache"]
        cls.Inventory = cls.env["stock.inventory"]

        cls.product_cola = cls.Product.create(
            {
                "name": "Refresco Cola 355ml",
                "default_code": "COLA-355",
                "barcode": "7460001112228",
                "type": "consu",
            }
        )
        cls.pack_box_24 = cls.Packaging.create(
            {
                "name": "Caja Master 24 Unidades",
                "product_id": cls.product_cola.id,
                "barcode": "17460001112225",
                "qty": 24.0,
                "qty_per_box": 24.0,
                "packaging_level": "master_box",
            }
        )

    def test_01_unit_vs_packaging_barcode_resolution(self):
        """Scanning unit barcode yields factor=1; scanning box barcode yields factor=24."""
        unit_res = self.Product.resolve_barcode_fast("7460001112228")
        self.assertTrue(unit_res["matched"])
        self.assertEqual(unit_res["match_type"], "unit")
        self.assertEqual(unit_res["unit_factor"], 1.0)
        self.assertEqual(unit_res["product_id"], self.product_cola.id)

        box_res = self.Product.resolve_barcode_fast("17460001112225")
        self.assertTrue(box_res["matched"])
        self.assertEqual(box_res["match_type"], "packaging")
        self.assertEqual(box_res["unit_factor"], 24.0)
        self.assertEqual(box_res["product_id"], self.product_cola.id)
        self.assertEqual(box_res["packaging_id"], self.pack_box_24.id)

    def test_02_inventory_session_multiplies_master_box_qty(self):
        """Scanning 2 master boxes (24 units each) + 3 single units = 51 total units."""
        stock_loc = self.env.ref("stock.stock_location_stock")
        inv = self.Inventory.create(
            {
                "name": "Conteo Cíclico Almacén Central",
                "location_id": stock_loc.id,
                "state": "in_progress",
            }
        )
        res = inv.action_process_barcode_batch(
            [
                {"barcode": "17460001112225", "qty": 2.0},  # 2 boxes * 24 = 48
                {"barcode": "7460001112228", "qty": 3.0},   # 3 units * 1 = 3
            ]
        )
        self.assertEqual(res["processed_count"], 2)
        self.assertEqual(res["total_units_added"], 51.0)
        line = inv.line_ids.filtered(lambda l: l.product_id == self.product_cola)
        self.assertEqual(len(line), 1)
        self.assertEqual(line.product_qty, 51.0)

    def test_03_typology_detection_and_external_enrichment(self):
        """Verify typology classifier (ITF-14, GS1 weight, EAN-13) and Open Food Facts fallback."""
        itf_info = self.Enrichment.detect_barcode_typology("17460001112225")
        self.assertEqual(itf_info["typology"], "ITF14")
        self.assertTrue(itf_info["is_master_box_candidate"])

        gs1_weight = self.Enrichment.detect_barcode_typology("2112345012504")
        self.assertEqual(gs1_weight["typology"], "GS1_WEIGHT")
        self.assertAlmostEqual(gs1_weight["embedded_weight_kg"], 1.250, places=3)

        mock_api_response = {
            "found": True,
            "name": "Café Santo Domingo Molido",
            "brand": "Induban",
            "weight_kg": 0.454,
            "uom_hint": "kg",
            "quantity_label": "454 g",
            "category_hint": "Groceries",
            "image_url": "",
            "suggested_box_qty": 1.0,
            "raw_payload": {"status": 1},
            "source_api": "openfoodfacts",
        }
        with patch.object(
            type(self.Enrichment),
            "_query_openfoodfacts",
            return_value=mock_api_response,
        ):
            unknown_code = "7460123456789"
            meta = self.Enrichment.fetch_external_product_metadata(unknown_code)
            self.assertTrue(meta["found"])
            self.assertEqual(meta["brand"], "Induban")

            cache_rec = self.Enrichment.search([("barcode", "=", unknown_code)], limit=1)
            created_payload = cache_rec.action_create_product_from_enrichment()
            self.assertTrue(created_payload["matched"])
            self.assertIn("Induban", created_payload["product_name"])
