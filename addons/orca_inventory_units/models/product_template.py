import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    orca_sold_by_pound = fields.Boolean(
        string="Se vende por libra",
        help="El precio de venta es el precio por libra. En el punto de venta se pregunta cuántas libras al elegir el producto.",
    )
    orca_units_per_box = fields.Float(
        string="Unidades por caja",
        digits=(16, 2),
        help="Si lo compra por caja y lo vende por unidad: cuántas unidades trae la caja. Déjelo en 0 si no aplica.",
    )
    orca_box_barcode = fields.Char(
        string="Código de barras de la caja",
        copy=False,
        help="Al escanearlo en el punto de venta o en inventario suma las unidades de la caja.",
    )

    @api.constrains("orca_units_per_box")
    def _check_orca_units_per_box(self):
        for rec in self:
            if rec.orca_units_per_box and rec.orca_units_per_box <= 1:
                raise ValidationError(_("Las unidades por caja deben ser más de 1 (o 0 si no se compra por caja)."))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._orca_sync_pound()
        records._orca_sync_box()
        return records

    def write(self, vals):
        res = super().write(vals)
        if "orca_sold_by_pound" in vals:
            self._orca_sync_pound(revert=True)
        if "orca_units_per_box" in vals or "orca_box_barcode" in vals:
            self._orca_sync_box()
        return res

    # ------------------------------------------------------------------ libra
    def _orca_sync_pound(self, revert=False):
        """Sold by pound: unit Libra, "to weigh" and available in the POS. Unchecked: back to Unidades."""
        pound = self.env.ref("uom.product_uom_lb", raise_if_not_found=False)
        unit = self.env.ref("uom.product_uom_unit", raise_if_not_found=False)
        if not pound:
            return
        for rec in self:
            if rec.orca_sold_by_pound:
                vals = {}
                if rec.uom_id != pound:
                    vals["uom_id"] = pound.id
                if "to_weight" in rec._fields and not rec.to_weight:
                    vals["to_weight"] = True
                if "available_in_pos" in rec._fields and not rec.available_in_pos:
                    vals["available_in_pos"] = True
                if vals:
                    rec.write(vals)
            elif revert and unit and rec.uom_id == pound:
                vals = {"uom_id": unit.id}
                if "to_weight" in rec._fields:
                    vals["to_weight"] = False
                rec.write(vals)

    # ------------------------------------------------------------------- caja
    def _orca_sync_box(self):
        """Box and unit related: unit "Caja xN" (purchase/receipt by box), POS barcode of the box (adds N units) and the
        packaging row of the inventory scanner. The product itself is sold by unit."""
        Uom = self.env["uom.uom"]
        for rec in self:
            n = rec.orca_units_per_box
            if not n or n <= 1:
                continue
            base = rec.uom_id
            label = int(n) if float(n).is_integer() else n
            box = Uom.search([("relative_uom_id", "=", base.id), ("relative_factor", "=", n)], limit=1)
            if not box:
                box = Uom.create({"name": f"Caja x{label}", "relative_uom_id": base.id, "relative_factor": n})
            if box not in rec.uom_ids:
                rec.uom_ids = [(4, box.id)]

            variant = rec.product_variant_id
            barcode = (rec.orca_box_barcode or "").strip()
            if not variant:
                continue
            if barcode:
                try:
                    with self.env.cr.savepoint():
                        line = self.env["product.uom"].search([("product_id", "=", variant.id), ("uom_id", "=", box.id)], limit=1)
                        if line:
                            line.barcode = barcode
                        else:
                            self.env["product.uom"].create({"product_id": variant.id, "uom_id": box.id, "barcode": barcode})
                except Exception as exc:
                    raise ValidationError(
                        _("No se pudo guardar el código de la caja (¿ya lo usa otro producto?): %s", exc)
                    ) from exc
            self._orca_mirror_scanner_packaging(variant, n, label, barcode)

    def _orca_mirror_scanner_packaging(self, variant, n, label, barcode):
        """The inventory scanner module keeps its own packaging table; keep it in step (never blocks the product)."""
        if "product.packaging" not in self.env:
            return
        try:
            with self.env.cr.savepoint():
                Pk = self.env["product.packaging"]
                row = Pk.search([("product_id", "=", variant.id), ("qty_per_box", "=", n)], limit=1)
                vals = {"name": f"Caja x{label}", "qty_per_box": n}
                if barcode:
                    vals["barcode"] = barcode
                if row:
                    row.write(vals)
                else:
                    vals["product_id"] = variant.id
                    if "packaging_level" in Pk._fields:
                        vals["packaging_level"] = "master_box"
                    Pk.create(vals)
        except Exception as exc:
            _logger.warning("orca_inventory_units: el empaque del escáner no se actualizó para %s: %s", variant.display_name, exc)
