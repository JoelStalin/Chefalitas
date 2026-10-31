import logging
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ProductProductBarcode(models.Model):
    _inherit = "product.product"

    barcode = fields.Char(
        string="Barcode",
        copy=False,
        index=True,
        help="International Article Number (EAN-13, UPC-A, GTIN) indexed in PostgreSQL for instant barcode lookup.",
    )
    orca_brand_name = fields.Char(
        string="Brand",
        index=True,
        help="Product brand enriched automatically or entered manually.",
    )
    orca_external_source = fields.Char(
        string="Enrichment Source",
        readonly=True,
        help="External catalog source (e.g., Open Food Facts) when created on the fly.",
    )

    def init(self):
        super().init()
        # Ensure partial B-Tree index on non-null barcodes for sub-millisecond PostgreSQL lookups
        self.env.cr.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_orca_product_product_barcode_notnull
            ON product_product (barcode)
            WHERE barcode IS NOT NULL AND active IS TRUE
            """
        )

    @api.model
    def resolve_barcode_fast(self, barcode):
        """High-speed indexed barcode lookup across product.product and product.packaging.

        Uses optimized search_read queries with minimal field projection to avoid ORM
        recordset instantiation overhead during continuous laser scanning.
        """
        clean_code = (barcode or "").strip()
        if not clean_code:
            return {"found": False, "match_type": "empty", "barcode": ""}

        # 1. Primary lookup: Unit barcode on product.product (indexed)
        products = self.search_read(
            domain=[("barcode", "=", clean_code), ("active", "=", True)],
            fields=["id", "display_name", "name", "default_code", "barcode", "uom_id", "weight", "tracking", "orca_brand_name"],
            limit=1,
        )
        if products:
            prod = products[0]
            uom_id = prod["uom_id"][0] if prod.get("uom_id") else False
            uom_name = prod["uom_id"][1] if prod.get("uom_id") else "Units"
            return {
                "found": True,
                "match_type": "product",
                "barcode": clean_code,
                "product_id": prod["id"],
                "product_name": prod.get("display_name") or prod["name"],
                "default_code": prod.get("default_code") or "",
                "brand": prod.get("orca_brand_name") or "",
                "uom_id": uom_id,
                "uom_name": uom_name,
                "weight": prod.get("weight") or 0.0,
                "tracking": prod.get("tracking") or "none",
                "packaging_id": False,
                "packaging_name": False,
                "package_level_type": "unit",
                "qty_per_box": 1.0,
                "resolved_qty": 1.0,
            }

        # 2. Secondary lookup: Multi-pack / Master Box barcode. Odoo 20 replaced product.packaging with
        # product.uom (product + packaging unit + barcode, indexed by Odoo itself).
        packagings = self._orca_packaging_rows([("barcode", "=", clean_code)], limit=1)
        if packagings:
            pkg = packagings[0]
            prod_tuple = pkg.get("product_id")
            if prod_tuple:
                prod_id = prod_tuple[0]
                prod_rows = self.search_read(
                    domain=[("id", "=", prod_id)],
                    fields=["id", "display_name", "name", "default_code", "barcode", "uom_id", "weight", "tracking", "orca_brand_name"],
                    limit=1,
                )
                prod = prod_rows[0] if prod_rows else {"id": prod_id, "name": prod_tuple[1]}
                factor = float(pkg.get("effective_unit_factor") or 1.0)
                if factor <= 0:
                    factor = 1.0
                uom_id = prod.get("uom_id")[0] if prod.get("uom_id") else False
                uom_name = prod.get("uom_id")[1] if prod.get("uom_id") else "Units"
                return {
                    "found": True,
                    "match_type": "packaging",
                    "barcode": clean_code,
                    "product_id": prod["id"],
                    "product_name": prod.get("display_name") or prod.get("name"),
                    "default_code": prod.get("default_code") or "",
                    "brand": prod.get("orca_brand_name") or "",
                    "uom_id": uom_id,
                    "uom_name": uom_name,
                    "weight": prod.get("weight") or 0.0,
                    "tracking": prod.get("tracking") or "none",
                    "packaging_id": pkg["id"],
                    "packaging_name": pkg["name"],
                    "package_level_type": pkg.get("package_level_type") or "master_box",
                    "qty_per_box": factor,
                    "resolved_qty": factor,
                }

        return {
            "found": False,
            "match_type": "not_found",
            "barcode": clean_code,
        }

    @api.model
    def _orca_packaging_rows(self, domain, limit=None, offset=0):
        """Packaging barcodes (product.uom) as plain dicts; ``name`` is the packaging unit's name."""
        rows = self.env["product.uom"].search_read(
            domain=domain,
            fields=["id", "barcode", "product_id", "uom_id", "effective_unit_factor", "package_level_type"],
            limit=limit,
            offset=offset,
            order="id asc",
        )
        for row in rows:
            row["name"] = row["uom_id"][1] if row.get("uom_id") else row["barcode"]
        return rows

    @api.model
    def warmup_barcode_catalog(self, limit=5000, offset=0, write_date_after=False):
        """Bulk-fetches active product and packaging barcodes using optimized search_read
        to populate the OWL client's IndexedDB cache for zero-RPC continuous scanning.
        """
        prod_domain = [("barcode", "!=", False), ("active", "=", True)]
        pkg_domain = [("barcode", "!=", False)]
        if write_date_after:
            prod_domain.append(("write_date", ">=", write_date_after))
            pkg_domain.append(("write_date", ">=", write_date_after))

        products = self.search_read(
            domain=prod_domain,
            fields=["id", "display_name", "name", "default_code", "barcode", "uom_id", "weight", "tracking", "orca_brand_name", "write_date"],
            limit=limit,
            offset=offset,
            order="id asc",
        )
        prod_by_id = {}
        entries = []
        for prod in products:
            prod_by_id[prod["id"]] = prod
            entries.append({
                "barcode": prod["barcode"],
                "found": True,
                "match_type": "product",
                "product_id": prod["id"],
                "product_name": prod.get("display_name") or prod["name"],
                "default_code": prod.get("default_code") or "",
                "brand": prod.get("orca_brand_name") or "",
                "uom_id": prod["uom_id"][0] if prod.get("uom_id") else False,
                "uom_name": prod["uom_id"][1] if prod.get("uom_id") else "Units",
                "weight": prod.get("weight") or 0.0,
                "tracking": prod.get("tracking") or "none",
                "packaging_id": False,
                "packaging_name": False,
                "package_level_type": "unit",
                "qty_per_box": 1.0,
                "resolved_qty": 1.0,
            })

        packagings = self._orca_packaging_rows(pkg_domain, limit=limit, offset=offset)
        missing_prod_ids = [
            p["product_id"][0]
            for p in packagings
            if p.get("product_id") and p["product_id"][0] not in prod_by_id
        ]
        if missing_prod_ids:
            extra_prods = self.search_read(
                domain=[("id", "in", list(set(missing_prod_ids)))],
                fields=["id", "display_name", "name", "default_code", "uom_id", "weight", "tracking", "orca_brand_name"],
            )
            for ep in extra_prods:
                prod_by_id[ep["id"]] = ep

        for pkg in packagings:
            if not pkg.get("product_id"):
                continue
            pid = pkg["product_id"][0]
            prod = prod_by_id.get(pid, {"id": pid, "name": pkg["product_id"][1]})
            factor = float(pkg.get("effective_unit_factor") or 1.0)
            if factor <= 0:
                factor = 1.0
            entries.append({
                "barcode": pkg["barcode"],
                "found": True,
                "match_type": "packaging",
                "product_id": pid,
                "product_name": prod.get("display_name") or prod.get("name"),
                "default_code": prod.get("default_code") or "",
                "brand": prod.get("orca_brand_name") or "",
                "uom_id": prod.get("uom_id")[0] if prod.get("uom_id") else False,
                "uom_name": prod.get("uom_id")[1] if prod.get("uom_id") else "Units",
                "weight": prod.get("weight") or 0.0,
                "tracking": prod.get("tracking") or "none",
                "packaging_id": pkg["id"],
                "packaging_name": pkg["name"],
                "package_level_type": pkg.get("package_level_type") or "master_box",
                "qty_per_box": factor,
                "resolved_qty": factor,
            })

        return {
            "count": len(entries),
            "synced_at": fields.Datetime.to_string(fields.Datetime.now()),
            "entries": entries,
        }


class ProductUomPackagingBarcode(models.Model):
    """Packaging barcode of a product (Odoo 20 ``product.uom``: product + packaging unit + barcode).

    The units per box come from the packaging unit itself (``uom.uom`` relative to the product unit), so multi-level
    hierarchies (pallet -> box -> unit) are the unit hierarchy Odoo already manages.
    """

    _inherit = "product.uom"

    package_level_type = fields.Selection(
        selection=[
            ("unit", "Single Unit (1x)"),
            ("inner_pack", "Inner Pack / Display"),
            ("master_box", "Master Box / Carton"),
            ("pallet", "Logistic Pallet / Skid"),
        ],
        string="Packaging Hierarchy Level",
        default="master_box",
        required=True,
    )
    effective_unit_factor = fields.Float(
        string="Total Base Units Multiplier",
        digits="Product Unit",
        compute="_compute_effective_unit_factor",
        store=True,
        help="Product base units contained in one packaging unit (1 packaging unit converted to the product unit).",
    )
    qty_per_box = fields.Float(related="effective_unit_factor", string="Units per Box (qty_per_box)")

    @api.depends("uom_id", "uom_id.factor", "product_id.uom_id", "product_id.uom_id.factor")
    def _compute_effective_unit_factor(self):
        for rec in self:
            base = rec.product_id.uom_id
            factor = rec.uom_id._compute_quantity(1.0, base, round=False) if rec.uom_id and base else 1.0
            rec.effective_unit_factor = factor if factor and factor > 0 else 1.0

    @api.constrains("uom_id", "product_id")
    def _check_positive_packaging_factor(self):
        for rec in self:
            if rec.uom_id and rec.product_id.uom_id and rec.uom_id._compute_quantity(1.0, rec.product_id.uom_id, round=False) <= 0:
                raise ValidationError(_("The packaging factor (qty_per_box) must be strictly greater than zero."))
