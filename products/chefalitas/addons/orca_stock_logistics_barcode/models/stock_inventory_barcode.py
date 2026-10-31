import logging
from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StockInventorySession(models.Model):
    """OCA stock-logistics-barcode compatible Inventory Adjustment Session for Odoo 20.

    Synchronizes directly with Odoo 20 native `stock.quant` records while providing
    structured session control, multi-packaging barcode multiplication, and audit trails.
    """

    _name = "stock.inventory"
    _description = "OCA / ORCA Barcode Inventory Adjustment Session (Odoo 20)"
    _inherit = ["barcodes.barcode_events_mixin"]
    _order = "date desc, id desc"

    name = fields.Char(
        string="Inventory Reference",
        required=True,
        default=lambda self: _("Inventory Barcode Session %s", fields.Date.context_today(self)),
        index=True,
    )
    date = fields.Datetime(
        string="Inventory Date",
        required=True,
        default=fields.Datetime.now,
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("confirm", "In Progress (Scanning)"),
            ("done", "Validated & Applied"),
            ("cancel", "Cancelled"),
        ],
        string="Status",
        default="draft",
        required=True,
        index=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Scanned Location",
        domain="[('usage', '=', 'internal')]",
        required=True,
        default=lambda self: self.env["stock.location"].search([("usage", "=", "internal")], limit=1),
    )
    line_ids = fields.One2many(
        comodel_name="stock.inventory.line",
        inverse_name="inventory_id",
        string="Inventory Count Lines",
    )
    scan_log_ids = fields.One2many(
        comodel_name="orca.stock.barcode.scan.log",
        inverse_name="inventory_id",
        string="Laser Scan History",
    )
    orca_last_scanned_barcode = fields.Char(string="Last Scanned Barcode", readonly=True)
    orca_total_barcode_scans = fields.Integer(string="Total Laser Scans", default=0, readonly=True)

    def action_start_inventory(self):
        for inv in self:
            if inv.state == "draft":
                inv.write({"state": "confirm", "date": fields.Datetime.now()})
        return True

    def action_open_orca_barcode_scanner(self):
        self.ensure_one()
        if self.state == "draft":
            self.action_start_inventory()
        return {
            "type": "ir.actions.client",
            "tag": "orca_stock_logistics_barcode.ScannerClientAction",
            "name": _("Inventory Scanner · %s", self.name),
            "context": {
                "default_model": "stock.inventory",
                "default_res_id": self.id,
            },
            "params": {
                "model": "stock.inventory",
                "res_id": self.id,
            },
        }

    def on_barcode_scanned(self, barcode):
        self.ensure_one()
        res = self.action_process_barcode_scan(barcode=barcode, scan_count=1.0, auto_enrich=True)
        if res.get("status") == "not_found":
            return {
                "warning": {
                    "title": _("Unknown Barcode: %s", barcode),
                    "message": res.get("message"),
                }
            }

    def _apply_resolved_barcode_to_inventory_lines(self, resolved, scan_count=1.0):
        self.ensure_one()
        if self.state in ("done", "cancel"):
            raise UserError(_("Cannot scan barcodes on a closed inventory session."))
        if self.state == "draft":
            self.action_start_inventory()

        product_id = resolved["product_id"]
        factor = float(resolved.get("qty_per_box") or resolved.get("resolved_qty") or 1.0)
        if factor <= 0:
            factor = 1.0
        added_qty = float(scan_count) * factor

        line = self.line_ids.filtered(
            lambda l: l.product_id.id == product_id and l.location_id.id == self.location_id.id
        )[:1]

        if line:
            line.write({
                "product_qty": line.product_qty + added_qty,
                "last_packaging_id": resolved.get("packaging_id") or line.last_packaging_id.id,
                "last_qty_per_box": factor,
            })
        else:
            # Query theoretical on-hand quantity from stock.quant
            quants = self.env["stock.quant"].search_read(
                domain=[
                    ("product_id", "=", product_id),
                    ("location_id", "=", self.location_id.id),
                ],
                fields=["quantity"],
            )
            theoretical_qty = sum(q.get("quantity") or 0.0 for q in quants)
            line = self.env["stock.inventory.line"].create({
                "inventory_id": self.id,
                "product_id": product_id,
                "location_id": self.location_id.id,
                "theoretical_qty": theoretical_qty,
                "product_qty": theoretical_qty + added_qty if theoretical_qty == 0 else added_qty,
                "last_packaging_id": resolved.get("packaging_id") or False,
                "last_qty_per_box": factor,
            })

        self.write({
            "orca_last_scanned_barcode": resolved["barcode"],
            "orca_total_barcode_scans": self.orca_total_barcode_scans + int(max(scan_count, 1)),
        })

        self.env["orca.stock.barcode.scan.log"].create({
            "barcode": resolved["barcode"],
            "match_type": resolved.get("match_type") if resolved.get("match_type") in ("product", "packaging") else "product",
            "inventory_id": self.id,
            "product_id": product_id,
            "packaging_id": resolved.get("packaging_id") or False,
            "scan_count": scan_count,
            "qty_per_box": factor,
            "total_units_added": added_qty,
        })

        return {
            "status": "ok",
            "inventory_id": self.id,
            "line_id": line.id,
            "barcode": resolved["barcode"],
            "match_type": resolved["match_type"],
            "product_id": product_id,
            "product_name": resolved["product_name"],
            "packaging_id": resolved.get("packaging_id") or False,
            "packaging_name": resolved.get("packaging_name") or False,
            "package_level_type": resolved.get("package_level_type") or "unit",
            "scan_count": scan_count,
            "qty_per_box": factor,
            "added_qty": added_qty,
            "line_total_qty": line.product_qty,
        }

    def action_process_barcode_scan(self, barcode, scan_count=1.0, auto_enrich=True, auto_create_enriched=False):
        self.ensure_one()
        Product = self.env["product.product"]
        resolved = Product.resolve_barcode_fast(barcode)

        if resolved.get("found"):
            return self._apply_resolved_barcode_to_inventory_lines(resolved, scan_count=scan_count)

        enrichment = {}
        if auto_enrich:
            EnrichmentCache = self.env["orca.barcode.enrichment.cache"]
            if auto_create_enriched:
                created_res = EnrichmentCache.action_create_product_from_enrichment(barcode)
                if created_res.get("found"):
                    applied = self._apply_resolved_barcode_to_inventory_lines(created_res, scan_count=scan_count)
                    applied["enriched_created"] = True
                    return applied
            else:
                enrichment = EnrichmentCache.fetch_external_product_metadata(barcode)

        return {
            "status": "not_found",
            "inventory_id": self.id,
            "barcode": (barcode or "").strip(),
            "enrichment": enrichment,
            "message": (
                _("Product not in local database. Found in %s: %s", enrichment.get("source_api"), enrichment.get("name"))
                if enrichment.get("found")
                else _("Barcode %s not found in Odoo or external catalogs.", barcode)
            ),
        }

    def action_process_barcode_batch(self, scans, auto_enrich=True, auto_create_enriched=False):
        self.ensure_one()
        results = []
        unknown_barcodes = []

        for item in scans or []:
            code = (item.get("barcode") or "").strip()
            count = float(item.get("count") or item.get("scan_count") or 1.0)
            if not code or count <= 0:
                continue
            res = self.action_process_barcode_scan(
                barcode=code,
                scan_count=count,
                auto_enrich=auto_enrich,
                auto_create_enriched=auto_create_enriched,
            )
            results.append(res)
            if res.get("status") == "not_found":
                unknown_barcodes.append(res)

        return {
            "inventory_id": self.id,
            "inventory_name": self.name,
            "processed_count": len(results),
            "unknown_count": len(unknown_barcodes),
            "results": results,
            "unknown_barcodes": unknown_barcodes,
            "picking_summary": self.get_barcode_scanner_state(),
        }

    def action_validate_inventory(self):
        """Applies counted quantities to Odoo 20 `stock.quant` inventory adjustment engine."""
        Quant = self.env["stock.quant"]
        for inv in self:
            for line in inv.line_ids:
                quant = Quant.search(
                    [
                        ("product_id", "=", line.product_id.id),
                        ("location_id", "=", line.location_id.id),
                        ("company_id", "=", inv.company_id.id),
                    ],
                    limit=1,
                )
                if not quant:
                    quant = Quant.create({
                        "product_id": line.product_id.id,
                        "location_id": line.location_id.id,
                        "company_id": inv.company_id.id,
                        "inventory_quantity": line.product_qty,
                    })
                else:
                    quant.inventory_quantity = line.product_qty
                if hasattr(quant, "action_apply_inventory"):
                    quant.action_apply_inventory()
            inv.write({"state": "done"})
        return True

    def get_barcode_scanner_state(self):
        self.ensure_one()
        lines = []
        for line in self.line_ids:
            lines.append({
                "move_id": line.id,
                "product_id": line.product_id.id,
                "product_name": line.product_id.display_name,
                "barcode": line.product_id.barcode or "",
                "default_code": line.product_id.default_code or "",
                "demand_qty": line.theoretical_qty,
                "qty_done": line.product_qty,
                "uom_name": line.product_uom_id.name,
                "packaging_name": line.last_packaging_id.name if line.last_packaging_id else "",
                "qty_per_box": line.last_qty_per_box or 1.0,
            })
        return {
            "id": self.id,
            "name": self.name,
            "model": "stock.inventory",
            "state": self.state,
            "location_name": self.location_id.complete_name,
            "location_dest_name": self.location_id.complete_name,
            "total_scans": self.orca_total_barcode_scans,
            "last_barcode": self.orca_last_scanned_barcode or "",
            "lines": lines,
        }


class StockInventoryLine(models.Model):
    _name = "stock.inventory.line"
    _description = "OCA / ORCA Barcode Inventory Count Line"

    inventory_id = fields.Many2one("stock.inventory", string="Inventory Session", required=True, ondelete="cascade", index=True)
    product_id = fields.Many2one("product.product", string="Product", required=True, index=True)
    product_uom_id = fields.Many2one("uom.uom", string="UoM", related="product_id.uom_id", store=True, readonly=True)
    location_id = fields.Many2one("stock.location", string="Location", required=True, index=True)
    theoretical_qty = fields.Float(string="On-Hand Theoretical Qty", digits="Product Unit of Measure", default=0.0, readonly=True)
    product_qty = fields.Float(string="Counted Quantity", digits="Product Unit of Measure", default=0.0)
    difference_qty = fields.Float(string="Difference", compute="_compute_difference_qty", store=True)
    last_packaging_id = fields.Many2one("product.packaging", string="Last Scanned Packaging")
    last_qty_per_box = fields.Float(string="Last Box Factor (qty_per_box)", default=1.0)

    @api.depends("product_qty", "theoretical_qty")
    def _compute_difference_qty(self):
        for line in self:
            line.difference_qty = (line.product_qty or 0.0) - (line.theoretical_qty or 0.0)


class StockQuantBarcodeExtension(models.Model):
    _inherit = "stock.quant"

    @api.model
    def action_scan_barcode_quant_adjustment(self, barcode, location_id, scan_count=1.0):
        """Direct fast barcode scan helper for Odoo 20 native `stock.quant` adjustments."""
        resolved = self.env["product.product"].resolve_barcode_fast(barcode)
        if not resolved.get("found"):
            return {"status": "not_found", "barcode": barcode}

        factor = float(resolved.get("qty_per_box") or 1.0)
        added_qty = float(scan_count) * factor
        quant = self.search(
            [
                ("product_id", "=", resolved["product_id"]),
                ("location_id", "=", location_id),
            ],
            limit=1,
        )
        if not quant:
            quant = self.create({
                "product_id": resolved["product_id"],
                "location_id": location_id,
                "inventory_quantity": added_qty,
            })
        else:
            base = quant.inventory_quantity if quant.inventory_quantity_set else quant.quantity
            quant.inventory_quantity = (base or 0.0) + added_qty
        return {
            "status": "ok",
            "quant_id": quant.id,
            "product_id": resolved["product_id"],
            "product_name": resolved["product_name"],
            "qty_per_box": factor,
            "added_qty": added_qty,
            "inventory_quantity": quant.inventory_quantity,
        }
