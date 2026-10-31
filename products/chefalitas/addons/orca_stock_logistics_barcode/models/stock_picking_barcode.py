import logging
from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class OrcaStockBarcodeScanLog(models.Model):
    _name = "orca.stock.barcode.scan.log"
    _description = "ORCA High-Speed Barcode Scan Audit Log"
    _order = "create_date desc, id desc"

    barcode = fields.Char(string="Scanned Code", required=True, index=True)
    match_type = fields.Selection(
        selection=[
            ("product", "Unit Barcode (1x)"),
            ("packaging", "Master Box / Multi-Packaging"),
            ("enriched_auto", "Enriched via External API"),
            ("unknown", "Unrecognized Barcode"),
        ],
        required=True,
        default="product",
    )
    picking_id = fields.Many2one("stock.picking", string="Stock Transfer", index=True, ondelete="cascade")
    inventory_id = fields.Many2one("stock.inventory", string="Inventory Session", index=True, ondelete="cascade")
    product_id = fields.Many2one("product.product", string="Product", index=True)
    packaging_id = fields.Many2one("product.packaging", string="Packaging Used")
    scan_count = fields.Float(string="Laser Scans", default=1.0)
    qty_per_box = fields.Float(string="Multiplier Factor (qty_per_box)", default=1.0)
    total_units_added = fields.Float(string="Total Base Units Registered", default=1.0)
    user_id = fields.Many2one("res.users", string="Operator", default=lambda self: self.env.user, index=True)


class StockPickingBarcode(models.Model):
    _name = "stock.picking"
    _inherit = ["stock.picking", "barcodes.barcode_events_mixin"]

    orca_last_scanned_barcode = fields.Char(
        string="Last Scanned Barcode",
        readonly=True,
        copy=False,
    )
    orca_total_barcode_scans = fields.Integer(
        string="Total Laser Scans",
        default=0,
        copy=False,
    )
    orca_scan_log_ids = fields.One2many(
        comodel_name="orca.stock.barcode.scan.log",
        inverse_name="picking_id",
        string="Barcode Scan Logs",
    )

    def on_barcode_scanned(self, barcode):
        """Standard Odoo barcode_events_mixin hook for form-view hardware scanner."""
        self.ensure_one()
        result = self.action_process_barcode_scan(barcode=barcode, scan_count=1.0, auto_enrich=True)
        if result.get("status") == "not_found":
            return {
                "warning": {
                    "title": _("Barcode Not Found: %s", barcode),
                    "message": result.get("message")
                    or _("No product or packaging matches barcode %s.", barcode),
                }
            }
        return

    def _apply_resolved_barcode_to_moves(self, resolved, scan_count=1.0):
        """Applies a resolved product or multi-packaging scan to the picking's stock moves.

        Automatically multiplies scan_count * qty_per_box when a Master Box / Packaging
        barcode is scanned.
        """
        self.ensure_one()
        if self.state in ("done", "cancel"):
            raise UserError(_("Cannot register barcode scans on a %s transfer.", self.state))

        product_id = resolved["product_id"]
        factor = float(resolved.get("qty_per_box") or resolved.get("resolved_qty") or 1.0)
        if factor <= 0:
            factor = 1.0
        added_qty = float(scan_count) * factor

        product = self.env["product.product"].browse(product_id)
        existing_moves = self.move_ids.filtered(
            lambda m: m.product_id.id == product_id and m.state not in ("done", "cancel")
        )

        if existing_moves:
            target_move = existing_moves[0]
            current_qty = target_move.quantity if "quantity" in target_move._fields else target_move.product_uom_qty
            new_qty = current_qty + added_qty
            update_vals = {}
            if "quantity" in target_move._fields:
                update_vals["quantity"] = new_qty
            if target_move.state == "draft":
                update_vals["product_uom_qty"] = max(target_move.product_uom_qty, new_qty)
            if "product_packaging_id" in target_move._fields and resolved.get("packaging_id"):
                update_vals["product_packaging_id"] = resolved["packaging_id"]
            if update_vals:
                target_move.write(update_vals)
        else:
            move_vals = {
                "name": product.display_name or product.name,
                "product_id": product.id,
                "product_uom": product.uom_id.id,
                "product_uom_qty": added_qty,
                "picking_id": self.id,
                "location_id": self.location_id.id,
                "location_dest_id": self.location_dest_id.id,
                "company_id": self.company_id.id,
            }
            if "quantity" in self.env["stock.move"]._fields:
                move_vals["quantity"] = added_qty
            if "product_packaging_id" in self.env["stock.move"]._fields and resolved.get("packaging_id"):
                move_vals["product_packaging_id"] = resolved["packaging_id"]
            target_move = self.env["stock.move"].create(move_vals)

        self.write({
            "orca_last_scanned_barcode": resolved["barcode"],
            "orca_total_barcode_scans": self.orca_total_barcode_scans + int(max(scan_count, 1)),
        })

        self.env["orca.stock.barcode.scan.log"].create({
            "barcode": resolved["barcode"],
            "match_type": resolved.get("match_type") if resolved.get("match_type") in ("product", "packaging") else "product",
            "picking_id": self.id,
            "product_id": product.id,
            "packaging_id": resolved.get("packaging_id") or False,
            "scan_count": scan_count,
            "qty_per_box": factor,
            "total_units_added": added_qty,
        })

        return {
            "status": "ok",
            "picking_id": self.id,
            "move_id": target_move.id,
            "barcode": resolved["barcode"],
            "match_type": resolved["match_type"],
            "product_id": product.id,
            "product_name": resolved["product_name"],
            "packaging_id": resolved.get("packaging_id") or False,
            "packaging_name": resolved.get("packaging_name") or False,
            "package_level_type": resolved.get("package_level_type") or "unit",
            "scan_count": scan_count,
            "qty_per_box": factor,
            "added_qty": added_qty,
            "move_total_qty": target_move.quantity if "quantity" in target_move._fields else target_move.product_uom_qty,
        }

    def action_process_barcode_scan(self, barcode, scan_count=1.0, auto_enrich=True, auto_create_enriched=False):
        """Processes a single barcode scan on a stock.picking, checking local indexed tables
        first (product.product & product.packaging) and falling back to Open Food Facts enrichment.
        """
        self.ensure_one()
        Product = self.env["product.product"]
        resolved = Product.resolve_barcode_fast(barcode)

        if resolved.get("found"):
            return self._apply_resolved_barcode_to_moves(resolved, scan_count=scan_count)

        enrichment = {}
        if auto_enrich:
            EnrichmentCache = self.env["orca.barcode.enrichment.cache"]
            if auto_create_enriched:
                created_res = EnrichmentCache.action_create_product_from_enrichment(barcode)
                if created_res.get("found"):
                    applied = self._apply_resolved_barcode_to_moves(created_res, scan_count=scan_count)
                    applied["enriched_created"] = True
                    return applied
            else:
                enrichment = EnrichmentCache.fetch_external_product_metadata(barcode)

        return {
            "status": "not_found",
            "picking_id": self.id,
            "barcode": (barcode or "").strip(),
            "enrichment": enrichment,
            "message": (
                _("Product not in local database. Found in %s: %s", enrichment.get("source_api"), enrichment.get("name"))
                if enrichment.get("found")
                else _("Barcode %s not found in Odoo or external catalogs.", barcode)
            ),
        }

    def action_process_barcode_batch(self, scans, auto_enrich=True, auto_create_enriched=False):
        """Processes a batch of consecutive laser gun scans flushed from the OWL IndexedDB buffer
        in a single atomic database transaction.

        :param scans: list of dicts [{'barcode': '...', 'count': 3}, ...]
        """
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
            "picking_id": self.id,
            "picking_name": self.name,
            "processed_count": len(results),
            "unknown_count": len(unknown_barcodes),
            "results": results,
            "unknown_barcodes": unknown_barcodes,
            "picking_summary": self.get_barcode_scanner_state(),
        }

    def get_barcode_scanner_state(self):
        """Returns a lightweight serialized snapshot of the picking lines for the OWL scanner UI."""
        self.ensure_one()
        lines = []
        for move in self.move_ids.filtered(lambda m: m.state != "cancel"):
            qty_done = move.quantity if "quantity" in move._fields else move.product_uom_qty
            pkg = move.product_packaging_id if "product_packaging_id" in move._fields else False
            lines.append({
                "move_id": move.id,
                "product_id": move.product_id.id,
                "product_name": move.product_id.display_name,
                "barcode": move.product_id.barcode or "",
                "default_code": move.product_id.default_code or "",
                "demand_qty": move.product_uom_qty,
                "qty_done": qty_done,
                "uom_name": move.product_uom.name,
                "packaging_name": pkg.name if pkg else "",
                "qty_per_box": pkg.qty_per_box if pkg and "qty_per_box" in pkg._fields else 1.0,
            })
        return {
            "id": self.id,
            "name": self.name,
            "model": "stock.picking",
            "state": self.state,
            "location_name": self.location_id.complete_name,
            "location_dest_name": self.location_dest_id.complete_name,
            "total_scans": self.orca_total_barcode_scans,
            "last_barcode": self.orca_last_scanned_barcode or "",
            "lines": lines,
        }

    def action_open_orca_barcode_scanner(self):
        """Opens the OWL High-Speed Laser Barcode Scanner client action for this picking."""
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "orca_stock_logistics_barcode.ScannerClientAction",
            "name": _("Barcode Scanner · %s", self.name),
            "context": {
                "default_model": "stock.picking",
                "default_res_id": self.id,
            },
            "params": {
                "model": "stock.picking",
                "res_id": self.id,
            },
        }
