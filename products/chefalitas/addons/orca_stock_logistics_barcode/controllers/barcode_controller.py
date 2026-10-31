from odoo import http
from odoo.http import request


class OrcaStockBarcodeController(http.Controller):
    @http.route("/orca/barcode/warmup", type="json", auth="user", methods=["POST"])
    def warmup_catalog(self, limit=5000, offset=0, write_date_after=False):
        return request.env["product.product"].warmup_barcode_catalog(
            limit=limit,
            offset=offset,
            write_date_after=write_date_after,
        )

    @http.route("/orca/barcode/resolve", type="json", auth="user", methods=["POST"])
    def resolve_barcode(self, barcode, auto_enrich=True):
        res = request.env["product.product"].resolve_barcode_fast(barcode)
        if not res.get("found") and auto_enrich:
            res["enrichment"] = request.env["orca.barcode.enrichment.cache"].fetch_external_product_metadata(barcode)
        return res

    @http.route("/orca/barcode/scan_batch", type="json", auth="user", methods=["POST"])
    def scan_batch(self, model, res_id, scans, auto_enrich=True, auto_create_enriched=False):
        if model not in ("stock.picking", "stock.inventory"):
            return {"status": "error", "message": f"Unsupported model: {model}"}
        record = request.env[model].browse(int(res_id)).exists()
        if not record:
            return {"status": "error", "message": "Target document not found"}
        return record.action_process_barcode_batch(
            scans=scans,
            auto_enrich=auto_enrich,
            auto_create_enriched=auto_create_enriched,
        )

    @http.route("/orca/barcode/create_enriched_product", type="json", auth="user", methods=["POST"])
    def create_enriched_product(self, barcode, custom_name=False, custom_brand=False, custom_weight=False, qty_per_box=False):
        return request.env["orca.barcode.enrichment.cache"].action_create_product_from_enrichment(
            barcode=barcode,
            custom_name=custom_name,
            custom_brand=custom_brand,
            custom_weight=custom_weight,
            qty_per_box=qty_per_box,
        )
