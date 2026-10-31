import json
import logging
import re
import urllib.error
import urllib.request
from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

WEIGHT_REGEX = re.compile(r"(\d+(?:[.,]\d+)?)\s*(kg|g|gr|ml|l|lt|oz|lb)\b", re.IGNORECASE)


class OrcaBarcodeEnrichmentCache(models.Model):
    _name = "orca.barcode.enrichment.cache"
    _description = "ORCA External Barcode Metadata & Typology Cache"
    _order = "write_date desc, id desc"

    barcode = fields.Char(string="Scanned Barcode", required=True, index=True)
    barcode_standard = fields.Selection(
        selection=[
            ("ean13", "EAN-13 / GTIN-13"),
            ("upca", "UPC-A / GTIN-12"),
            ("ean8", "EAN-8 / GTIN-8"),
            ("itf14", "ITF-14 / DUN-14 (Master Box)"),
            ("gs1_weight", "GS1 Variable Weight/Measure"),
            ("gs1_128", "GS1-128 Logistic Label"),
            ("code128", "Code-128 / Internal SKU"),
        ],
        string="Detected Typology",
        default="ean13",
        required=True,
    )
    is_master_pack_barcode = fields.Boolean(
        string="Is Logistic Box Barcode",
        default=False,
        help="True when barcode typology indicates an ITF-14 / DUN-14 master carton.",
    )
    inferred_unit_barcode = fields.Char(
        string="Inferred Unit GTIN",
        help="For ITF-14 master cartons, the inner 13-digit EAN of the base unit.",
    )
    inferred_qty_per_box = fields.Float(
        string="Inferred Box Factor",
        default=1.0,
    )
    product_name = fields.Char(string="Suggested Product Name")
    brand = fields.Char(string="Brand")
    weight = fields.Float(string="Weight (kg)", digits="Stock Weight")
    quantity_label = fields.Char(string="Declared Net Quantity (e.g., 500 g)")
    uom_name = fields.Char(string="Suggested UoM", default="Units")
    category_name = fields.Char(string="Category")
    image_url = fields.Char(string="External Image URL")
    source_api = fields.Char(string="Source API", default="openfoodfacts")
    raw_payload_json = fields.Text(string="Raw API Payload")
    product_id = fields.Many2one("product.product", string="Linked Odoo Product", index=True)
    state = fields.Selection(
        selection=[
            ("enriched", "Metadata Enriched"),
            ("not_found", "Not Found in Public API"),
            ("product_created", "Product Created in Odoo"),
        ],
        default="enriched",
        required=True,
    )

    @api.model
    def detect_barcode_typology(self, barcode):
        """Analyzes barcode structure to classify standard (EAN-13, UPC-A, ITF-14, GS1 Variable Weight)
        and extract embedded logistics/weight metadata before hitting external APIs.
        """
        code = (barcode or "").strip()
        digits_only = code.isdigit()
        length = len(code)

        # 1. ITF-14 / DUN-14 Master Box (14 digits starting with packaging indicator 1..8)
        if digits_only and length == 14:
            indicator = int(code[0])
            inner_ean13 = code[1:13]
            # Calculate standard EAN-13 check digit for the inner 12 digits
            evens = sum(int(inner_ean13[i]) for i in range(1, 12, 2))
            odds = sum(int(inner_ean13[i]) for i in range(0, 12, 2))
            check = (10 - ((odds + evens * 3) % 10)) % 10
            unit_ean13 = f"{inner_ean13}{check}"
            default_box_factors = {1: 6.0, 2: 12.0, 3: 24.0, 4: 48.0, 5: 100.0}
            return {
                "barcode": code,
                "barcode_standard": "itf14",
                "is_master_pack_barcode": indicator > 0,
                "inferred_unit_barcode": unit_ean13,
                "inferred_qty_per_box": default_box_factors.get(indicator, 12.0),
                "embedded_weight_kg": 0.0,
            }

        # 2. GS1 Variable Weight EAN-13 (Prefix 20-29: 2PPPPPPWWWWWC)
        if digits_only and length == 13 and code[:2] in {str(i) for i in range(20, 30)}:
            weight_grams = int(code[7:12])
            return {
                "barcode": code,
                "barcode_standard": "gs1_weight",
                "is_master_pack_barcode": False,
                "inferred_unit_barcode": code[:7] + "000000",
                "inferred_qty_per_box": 1.0,
                "embedded_weight_kg": round(weight_grams / 1000.0, 3),
            }

        if digits_only and length == 13:
            return {
                "barcode": code,
                "barcode_standard": "ean13",
                "is_master_pack_barcode": False,
                "inferred_unit_barcode": code,
                "inferred_qty_per_box": 1.0,
                "embedded_weight_kg": 0.0,
            }

        if digits_only and length == 12:
            return {
                "barcode": code,
                "barcode_standard": "upca",
                "is_master_pack_barcode": False,
                "inferred_unit_barcode": code,
                "inferred_qty_per_box": 1.0,
                "embedded_weight_kg": 0.0,
            }

        if digits_only and length == 8:
            return {
                "barcode": code,
                "barcode_standard": "ean8",
                "is_master_pack_barcode": False,
                "inferred_unit_barcode": code,
                "inferred_qty_per_box": 1.0,
                "embedded_weight_kg": 0.0,
            }

        if length > 14 and ("(" in code or code.startswith("01")):
            return {
                "barcode": code,
                "barcode_standard": "gs1_128",
                "is_master_pack_barcode": True,
                "inferred_unit_barcode": code[2:16] if code.startswith("01") and len(code) >= 16 else code,
                "inferred_qty_per_box": 1.0,
                "embedded_weight_kg": 0.0,
            }

        return {
            "barcode": code,
            "barcode_standard": "code128",
            "is_master_pack_barcode": False,
            "inferred_unit_barcode": code,
            "inferred_qty_per_box": 1.0,
            "embedded_weight_kg": 0.0,
        }

    @api.model
    def _parse_quantity_to_weight_and_uom(self, quantity_str, net_weight_value=None, net_weight_unit=None):
        """Extracts normalized weight in kilograms and UoM label from Open Food Facts quantity strings."""
        if net_weight_value:
            try:
                val = float(net_weight_value)
                unit = (net_weight_unit or "g").lower().strip()
                if unit in ("g", "gr", "ml"):
                    return round(val / 1000.0, 4), "Units"
                if unit in ("kg", "l", "lt"):
                    return round(val, 4), "Units"
            except (ValueError, TypeError):
                pass

        text = (quantity_str or "").strip()
        if not text:
            return 0.0, "Units"

        match = WEIGHT_REGEX.search(text)
        if not match:
            return 0.0, "Units"

        raw_val = float(match.group(1).replace(",", "."))
        unit = match.group(2).lower()
        if unit in ("g", "gr", "ml"):
            return round(raw_val / 1000.0, 4), "Units"
        if unit in ("kg", "l", "lt"):
            return round(raw_val, 4), "Units"
        if unit == "oz":
            return round(raw_val * 0.0283495, 4), "Units"
        if unit == "lb":
            return round(raw_val * 0.453592, 4), "Units"
        return 0.0, "Units"

    @api.model
    def fetch_external_product_metadata(self, barcode, timeout=3.5):
        """Queries public APIs (Open Food Facts v2 -> Open Products Facts fallback)
        for unknown barcodes and caches the enriched result in PostgreSQL.
        """
        clean_code = (barcode or "").strip()
        if not clean_code:
            return {"found": False, "barcode": ""}

        # 1. Check local enrichment cache first (indexed)
        cached = self.search_read(
            domain=[("barcode", "=", clean_code)],
            fields=[
                "id",
                "barcode",
                "barcode_standard",
                "is_master_pack_barcode",
                "inferred_unit_barcode",
                "inferred_qty_per_box",
                "product_name",
                "brand",
                "weight",
                "quantity_label",
                "uom_name",
                "category_name",
                "image_url",
                "source_api",
                "product_id",
                "state",
            ],
            limit=1,
        )
        if cached and cached[0].get("state") in ("enriched", "product_created"):
            row = cached[0]
            return {
                "found": True,
                "cached": True,
                "cache_id": row["id"],
                "barcode": row["barcode"],
                "barcode_standard": row["barcode_standard"],
                "is_master_pack_barcode": row["is_master_pack_barcode"],
                "inferred_unit_barcode": row["inferred_unit_barcode"],
                "inferred_qty_per_box": row["inferred_qty_per_box"],
                "name": row["product_name"],
                "brand": row["brand"] or "",
                "weight": row["weight"] or 0.0,
                "quantity_label": row["quantity_label"] or "",
                "uom_name": row["uom_name"] or "Units",
                "category_name": row["category_name"] or "",
                "image_url": row["image_url"] or "",
                "source_api": row["source_api"],
                "product_id": row["product_id"][0] if row.get("product_id") else False,
            }

        typology = self.detect_barcode_typology(clean_code)
        lookup_codes = [clean_code]
        if typology["is_master_pack_barcode"] and typology["inferred_unit_barcode"] != clean_code:
            lookup_codes.append(typology["inferred_unit_barcode"])

        endpoints = [
            ("openfoodfacts", "https://world.openfoodfacts.org/api/v2/product/{code}.json"),
            ("openproductsfacts", "https://world.openproductsfacts.org/api/v2/product/{code}.json"),
        ]

        headers = {
            "User-Agent": "ORCA-ERP-Odoo20-BarcodeScanner/1.0 (https://getupsoft.com)",
            "Accept": "application/json",
        }

        for query_code in lookup_codes:
            for source_name, url_tpl in endpoints:
                url = url_tpl.format(code=urllib.parse.quote(query_code))
                try:
                    req = urllib.request.Request(url, headers=headers, method="GET")
                    with urllib.request.urlopen(req, timeout=timeout) as response:
                        if response.status != 200:
                            continue
                        payload = json.loads(response.read().decode("utf-8", errors="replace"))
                except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
                    _logger.debug("External barcode enrichment skipped for %s on %s: %s", query_code, source_name, exc)
                    continue

                if payload.get("status") == 1 and isinstance(payload.get("product"), dict):
                    p_data = payload["product"]
                    raw_name = (
                        p_data.get("product_name_es")
                        or p_data.get("product_name")
                        or p_data.get("generic_name_es")
                        or p_data.get("generic_name")
                        or ""
                    ).strip()
                    brand = (p_data.get("brands") or "").split(",")[0].strip()
                    quantity_label = (p_data.get("quantity") or "").strip()
                    weight_kg, uom_name = self._parse_quantity_to_weight_and_uom(
                        quantity_label,
                        net_weight_value=p_data.get("product_quantity"),
                        net_weight_unit=p_data.get("product_quantity_unit"),
                    )
                    if not weight_kg and typology.get("embedded_weight_kg"):
                        weight_kg = typology["embedded_weight_kg"]

                    full_name = raw_name
                    if brand and brand.lower() not in full_name.lower():
                        full_name = f"{raw_name} - {brand}" if raw_name else brand
                    if quantity_label and quantity_label.lower() not in full_name.lower():
                        full_name = f"{full_name} ({quantity_label})".strip()
                    if not full_name:
                        full_name = f"Product {clean_code}"

                    categories = (p_data.get("categories") or "").split(",")[0].strip()
                    image_url = p_data.get("image_front_small_url") or p_data.get("image_url") or ""

                    vals = {
                        "barcode": clean_code,
                        "barcode_standard": typology["barcode_standard"],
                        "is_master_pack_barcode": typology["is_master_pack_barcode"],
                        "inferred_unit_barcode": typology["inferred_unit_barcode"],
                        "inferred_qty_per_box": typology["inferred_qty_per_box"],
                        "product_name": full_name,
                        "brand": brand,
                        "weight": weight_kg,
                        "quantity_label": quantity_label,
                        "uom_name": uom_name,
                        "category_name": categories,
                        "image_url": image_url,
                        "source_api": source_name,
                        "raw_payload_json": json.dumps(
                            {
                                "code": query_code,
                                "product_name": raw_name,
                                "brands": brand,
                                "quantity": quantity_label,
                                "categories": categories,
                            },
                            ensure_ascii=False,
                        ),
                        "state": "enriched",
                    }
                    existing_rec = self.search([("barcode", "=", clean_code)], limit=1)
                    if existing_rec:
                        existing_rec.write(vals)
                        rec = existing_rec
                    else:
                        rec = self.create(vals)

                    return {
                        "found": True,
                        "cached": False,
                        "cache_id": rec.id,
                        "barcode": clean_code,
                        "barcode_standard": typology["barcode_standard"],
                        "is_master_pack_barcode": typology["is_master_pack_barcode"],
                        "inferred_unit_barcode": typology["inferred_unit_barcode"],
                        "inferred_qty_per_box": typology["inferred_qty_per_box"],
                        "name": full_name,
                        "brand": brand,
                        "weight": weight_kg,
                        "quantity_label": quantity_label,
                        "uom_name": uom_name,
                        "category_name": categories,
                        "image_url": image_url,
                        "source_api": source_name,
                        "product_id": False,
                    }

        return {
            "found": False,
            "cached": False,
            "barcode": clean_code,
            "barcode_standard": typology["barcode_standard"],
            "is_master_pack_barcode": typology["is_master_pack_barcode"],
            "inferred_unit_barcode": typology["inferred_unit_barcode"],
            "inferred_qty_per_box": typology["inferred_qty_per_box"],
            "weight": typology.get("embedded_weight_kg") or 0.0,
        }

    @api.model
    def action_create_product_from_enrichment(
        self,
        barcode,
        custom_name=False,
        custom_brand=False,
        custom_weight=False,
        qty_per_box=False,
    ):
        """Creates a product.product (and product.packaging if Master Box / ITF-14) on the fly
        from enriched metadata, returning the ready-to-scan resolution dictionary.
        """
        clean_code = (barcode or "").strip()
        if not clean_code:
            raise UserError(_("A valid barcode is required to create a product on the fly."))

        # Verify if already created
        existing = self.env["product.product"].resolve_barcode_fast(clean_code)
        if existing.get("found"):
            return existing

        enriched = self.fetch_external_product_metadata(clean_code)
        typology = self.detect_barcode_typology(clean_code)

        name = (custom_name or enriched.get("name") or f"Producto {clean_code}").strip()
        brand = (custom_brand if custom_brand is not None else enriched.get("brand") or "").strip()
        weight = float(custom_weight if custom_weight is not None and custom_weight is not False else (enriched.get("weight") or 0.0))
        is_box = bool(enriched.get("is_master_pack_barcode") or (qty_per_box and float(qty_per_box) > 1.0))
        box_factor = float(qty_per_box or enriched.get("inferred_qty_per_box") or 1.0)

        unit_barcode = typology["inferred_unit_barcode"] if is_box and typology["inferred_unit_barcode"] != clean_code else clean_code

        # Check if base unit product already exists when scanning an ITF-14 Master Box
        Product = self.env["product.product"]
        unit_prod = Product.search([("barcode", "=", unit_barcode)], limit=1) if is_box else Product.browse()

        if not unit_prod:
            prod_vals = {
                "name": name,
                "type": "consu",
                "is_storable": True,
                "barcode": False if is_box and unit_barcode == clean_code else unit_barcode,
                "weight": weight,
                "orca_brand_name": brand,
                "orca_external_source": enriched.get("source_api") or "manual_fast_create",
            }
            # Fallback if is_storable is not present in custom product inheritance
            if "is_storable" not in Product._fields:
                prod_vals.pop("is_storable", None)
                prod_vals["type"] = "product"
            unit_prod = Product.create(prod_vals)

        if is_box and box_factor > 1.0:
            self.env["product.packaging"].create({
                "name": f"Master Box x{int(box_factor) if box_factor.is_integer() else box_factor}",
                "product_id": unit_prod.id,
                "barcode": clean_code,
                "package_level_type": "master_box",
                "qty": box_factor,
                "qty_per_box": box_factor,
            })

        cache_rec = self.search([("barcode", "=", clean_code)], limit=1)
        if cache_rec:
            cache_rec.write({"product_id": unit_prod.id, "state": "product_created"})

        return Product.resolve_barcode_fast(clean_code)
