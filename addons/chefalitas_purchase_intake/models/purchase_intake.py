"""Supplier invoice photo received over WhatsApp -> ORCA reading -> employee confirmation -> purchase order,
receipt (stock in) and draft vendor bill with the photo attached."""
import base64
import logging
import re

import requests
from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

TIMEOUT = 120
YES = {"si", "sí", "ok", "confirmo", "correcto", "yes"}
NO = {"no", "cancelar", "cancela", "anular"}
CORRECTION = re.compile(r"^\s*l[ií]nea\s+(\d+)\s+(cantidad|precio|producto)\s+(.+?)\s*$", re.I)


class PurchaseIntake(models.Model):
    _name = "purchase.intake"
    _description = "Factura de compra recibida por WhatsApp"
    _inherit = ["mail.thread"]
    _order = "id desc"

    name = fields.Char(default="/", readonly=True, copy=False)
    state = fields.Selection([
        ("received", "Recibida"),
        ("awaiting_confirmation", "Esperando confirmación"),
        ("done", "Registrada"),
        ("rejected", "Descartada"),
        ("error", "Error de lectura"),
    ], default="received", required=True, tracking=True, index=True)
    channel_id = fields.Many2one("discuss.channel", readonly=True)
    sender_id = fields.Many2one("res.partner", "Enviada por", readonly=True)
    attachment_id = fields.Many2one("ir.attachment", "Imagen", readonly=True)
    reader = fields.Char("Leída con", readonly=True, help="ORCA layer that produced the reading (ocr+local, cloud...)")
    confidence = fields.Float(readonly=True)
    vendor_vat = fields.Char("RNC proveedor")
    vendor_name = fields.Char("Proveedor")
    ncf = fields.Char("NCF")
    invoice_date = fields.Date("Fecha factura")
    amount_tax = fields.Float("ITBIS")
    amount_total = fields.Float("Total")
    line_ids = fields.One2many("purchase.intake.line", "intake_id")
    purchase_id = fields.Many2one("purchase.order", readonly=True)
    bill_id = fields.Many2one("account.move", "Factura de proveedor", readonly=True)
    error = fields.Char(readonly=True)

    # ------------------------------------------------------------------ WhatsApp entry point
    @api.model
    def _on_whatsapp_message(self, channel, message):
        sender = message.author_id
        if not sender.purchase_intake_allowed:
            return False
        images = message.attachment_ids.filtered(lambda a: (a.mimetype or "").startswith("image/"))
        if images:
            intake = self.create({"channel_id": channel.id, "sender_id": sender.id, "attachment_id": images[0].id})
            intake._read_invoice()
            return intake
        pending = self.search([("channel_id", "=", channel.id), ("state", "=", "awaiting_confirmation")], limit=1)
        if pending:
            pending._handle_reply(message.preview or "")
            return pending
        return False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = self.env["ir.sequence"].next_by_code("purchase.intake") or "/"
        return super().create(vals_list)

    # ------------------------------------------------------------------ reading (ORCA)
    def _orca_extract(self, image_b64, mimetype):
        """Ask ORCA to read the invoice. ORCA picks the layer (local OCR + local model, cloud if configured)."""
        client = self.env["orca.bridge.client"]
        settings = client._settings()
        if not settings["url"]:
            raise UserError(_("ORCA is not configured (Settings > ORCA)."))
        response = requests.post(
            f"{settings['url']}/api/orca/purchase-intake/extract",
            json={"image_base64": image_b64, "mimetype": mimetype, "company_vat": self.env.company.vat},
            headers={"Authorization": f"Bearer {client._access_token()}"},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    def _read_invoice(self):
        self.ensure_one()
        try:
            data = self._orca_extract(base64.b64encode(self.attachment_id.raw).decode(), self.attachment_id.mimetype)
        except Exception as exc:  # noqa: BLE001 - the employee is told, nothing is created
            _logger.warning("purchase intake %s: ORCA reading failed: %s", self.name, exc)
            self.write({"state": "error", "error": str(exc)[:250]})
            self._reply(_("No pude leer la factura (%s). Envíe una foto más clara o regístrela manualmente.", self.name))
            return
        self._apply_reading(data)
        self.state = "awaiting_confirmation"
        self._reply(self._summary())

    def _apply_reading(self, data):
        vendor = data.get("vendor") or {}
        self.line_ids.unlink()
        self.write({
            "reader": data.get("reader"), "confidence": data.get("confidence") or 0.0,
            "vendor_vat": vendor.get("vat"), "vendor_name": vendor.get("name"), "ncf": data.get("ncf"),
            "invoice_date": data.get("date") or False,
            "amount_tax": data.get("amount_tax") or 0.0, "amount_total": data.get("amount_total") or 0.0,
            "line_ids": [(0, 0, {
                "sequence": i, "description": l.get("description") or "?",
                "quantity": l.get("quantity") or 1.0, "price_unit": l.get("price_unit") or 0.0,
                "tax_rate": l.get("tax_rate") if l.get("tax_rate") is not None else 18.0,
            }) for i, l in enumerate(data.get("lines") or [], start=1)],
        })
        self.line_ids._match_products(self._vendor())

    def _summary(self):
        lines = "\n".join(
            f"{l.sequence}. {l.description} — {l.quantity:g} x {l.price_unit:,.2f}"
            + (f" → {l.product_id.display_name}" if l.product_id else " → (producto nuevo)")
            for l in self.line_ids)
        return _(
            "%(name)s\nProveedor: %(vendor)s (RNC %(vat)s)\nNCF: %(ncf)s  Fecha: %(date)s\n%(lines)s\n"
            "ITBIS: %(tax).2f  Total: %(total).2f\n\n"
            "Responda SI para registrar, NO para descartar, o corrija: \"linea 2 cantidad 5\", "
            "\"linea 1 precio 120\", \"linea 3 producto Pollo\".",
            name=self.name, vendor=self.vendor_name or "?", vat=self.vendor_vat or "?", ncf=self.ncf or "?",
            date=self.invoice_date or "?", lines=lines, tax=self.amount_tax, total=self.amount_total)

    # ------------------------------------------------------------------ conversation
    def _handle_reply(self, text):
        self.ensure_one()
        word = text.strip().lower().rstrip(".!")
        if word in YES:
            try:
                self._register_purchase()
            except Exception as exc:  # noqa: BLE001 - keep the intake, tell the employee
                _logger.exception("purchase intake %s: registration failed", self.name)
                self._reply(_("No pude registrar %(name)s: %(err)s", name=self.name, err=str(exc)[:200]))
                return
            self._reply(_("%(name)s registrada: orden %(po)s, mercancía recibida, factura %(bill)s en borrador.",
                          name=self.name, po=self.purchase_id.name, bill=self.bill_id.display_name))
            return
        if word in NO:
            self.state = "rejected"
            self._reply(_("%s descartada.", self.name))
            return
        match = CORRECTION.match(text)
        if not match:
            self._reply(_("No entendí. Responda SI, NO o una corrección como \"linea 2 cantidad 5\"."))
            return
        number, field, value = int(match.group(1)), match.group(2).lower(), match.group(3)
        line = self.line_ids.filtered(lambda l: l.sequence == number)
        if not line:
            self._reply(_("No existe la línea %s.", number))
            return
        if field in ("cantidad", "precio"):
            try:
                amount = float(value.replace(",", ""))
            except ValueError:
                self._reply(_("\"%s\" no es un número.", value))
                return
            line.write({"quantity" if field == "cantidad" else "price_unit": amount})
        else:
            product = self.env["product.product"].search([("name", "ilike", value), ("purchase_ok", "=", True)], limit=1)
            if not product:
                self._reply(_("No encontré el producto \"%s\".", value))
                return
            line.product_id = product
        self._reply(self._summary())

    def _reply(self, text):
        """Answer in the same WhatsApp conversation (free-form message inside the 24 h window)."""
        if self.channel_id:
            self.channel_id.message_post(body=Markup("<br/>").join(escape(t) for t in text.split("\n")),
                                         message_type="whatsapp_message")

    # ------------------------------------------------------------------ registration in Odoo
    def _vendor(self):
        Partner = self.env["res.partner"]
        if self.vendor_vat:
            vendor = Partner.search([("vat", "=", self.vendor_vat)], limit=1)
            if vendor:
                return vendor
        return Partner

    def _register_purchase(self):
        self.ensure_one()
        vendor = self._vendor() or self.env["res.partner"].create(
            {"name": self.vendor_name or self.vendor_vat or _("Proveedor sin nombre"), "vat": self.vendor_vat,
             "is_company": True, "supplier_rank": 1})
        self.line_ids._create_missing_products()
        order = self.env["purchase.order"].create({
            "partner_id": vendor.id, "partner_ref": self.ncf, "date_order": fields.Datetime.now(),
            "order_line": [(0, 0, {
                "product_id": l.product_id.id, "name": l.description, "product_qty": l.quantity,
                "price_unit": l.price_unit, "tax_ids": [(6, 0, l._purchase_taxes().ids)],
            }) for l in self.line_ids],
        })
        order.button_confirm()
        for picking in order.picking_ids.filtered(lambda p: p.state not in ("done", "cancel")):
            for move in picking.move_ids:
                move.quantity = move.product_uom_qty
                move.picked = True
            picking.button_validate()
        order.action_create_invoice()
        bill = order.invoice_ids[:1]
        bill.write({"ref": self.ncf, "invoice_date": self.invoice_date or fields.Date.today()})
        copy = self.attachment_id.copy({"res_model": "account.move", "res_id": bill.id})
        bill.message_post(body=_("Factura recibida por WhatsApp (%s).", self.name), attachment_ids=copy.ids)
        order.message_post(body=_("Factura recibida por WhatsApp (%s).", self.name),
                           attachment_ids=self.attachment_id.copy({"res_model": "purchase.order", "res_id": order.id}).ids)
        self.line_ids._remember_vendor_names(vendor)
        self.write({"state": "done", "purchase_id": order.id, "bill_id": bill.id})


class PurchaseIntakeLine(models.Model):
    _name = "purchase.intake.line"
    _description = "Línea de factura de compra recibida por WhatsApp"
    _order = "sequence"

    intake_id = fields.Many2one("purchase.intake", required=True, ondelete="cascade")
    sequence = fields.Integer()
    description = fields.Char(required=True)
    quantity = fields.Float(default=1.0)
    price_unit = fields.Float()
    tax_rate = fields.Float(default=18.0)
    product_id = fields.Many2one("product.product")

    def _match_products(self, vendor):
        """Learned vendor names first (product.supplierinfo), then the product name."""
        for line in self.filtered(lambda l: not l.product_id):
            info = self.env["product.supplierinfo"].search(
                [("partner_id", "=", vendor.id), ("product_name", "=ilike", line.description)], limit=1) if vendor else None
            product = info and (info.product_id or info.product_tmpl_id.product_variant_id)
            if not product:
                product = self.env["product.product"].search(
                    [("name", "=ilike", line.description), ("purchase_ok", "=", True)], limit=1)
            line.product_id = product or False

    def _create_missing_products(self):
        for line in self.filtered(lambda l: not l.product_id):
            line.product_id = self.env["product.product"].create({
                "name": line.description, "type": "consu", "is_storable": True, "purchase_ok": True,
                "sale_ok": False, "standard_price": line.price_unit,
            })

    def _purchase_taxes(self):
        if not self.tax_rate:
            return self.env["account.tax"]
        return self.env["account.tax"].search([
            ("type_tax_use", "=", "purchase"), ("amount", "=", self.tax_rate), ("amount_type", "=", "percent"),
            ("company_id", "=", self.env.company.id)], limit=1)

    def _remember_vendor_names(self, vendor):
        for line in self:
            exists = self.env["product.supplierinfo"].search_count([
                ("partner_id", "=", vendor.id), ("product_tmpl_id", "=", line.product_id.product_tmpl_id.id),
                ("product_name", "=ilike", line.description)])
            if not exists:
                self.env["product.supplierinfo"].create({
                    "partner_id": vendor.id, "product_tmpl_id": line.product_id.product_tmpl_id.id,
                    "product_name": line.description, "price": line.price_unit})
