import hashlib
import hmac
import secrets
import uuid
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class ScaleDevice(models.Model):
    _name = "pos.scale.device"
    _description = "POS Scale Gateway Device"

    name = fields.Char(required=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    active = fields.Boolean(default=True)
    pairing_hash = fields.Char(copy=False, groups="point_of_sale.group_pos_manager")
    pairing_expires_at = fields.Datetime(copy=False, groups="point_of_sale.group_pos_manager")
    pairing_failures = fields.Integer(default=0, copy=False, groups="point_of_sale.group_pos_manager")
    token_hash = fields.Char(copy=False, groups="point_of_sale.group_pos_manager")
    last_reading_id = fields.Many2one("pos.scale.reading", readonly=True, copy=False)
    consumed_sample_id = fields.Char(copy=False, readonly=True)
    connected = fields.Boolean(compute="_compute_connected")

    def _compute_connected(self):
        now = fields.Datetime.now()
        for device in self:
            reading = device.last_reading_id
            device.connected = bool(reading and (now - reading.create_date).total_seconds() <= 30)

    def action_pair(self):
        self.ensure_one()
        if not self.env.user.has_group("point_of_sale.group_pos_manager"):
            raise AccessError(_("Only POS managers may pair scales."))
        code = "".join(str(secrets.randbelow(10)) for _ in range(10))
        self.write({
            "pairing_hash": digest(code),
            "pairing_expires_at": fields.Datetime.now() + timedelta(minutes=10),
            "pairing_failures": 0,
            "token_hash": False,
            "consumed_sample_id": False,
        })
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Scale pairing code"),
                "message": _("Device %(device)s: %(code)s (valid for 10 minutes).", device=self.name, code=code),
                "type": "warning",
                "sticky": True,
            },
        }

    def action_revoke(self):
        if not self.env.user.has_group("point_of_sale.group_pos_manager"):
            raise AccessError(_("Only POS managers may revoke scales."))
        self.write({"token_hash": False, "pairing_hash": False, "pairing_expires_at": False})

    def exchange_pairing_code(self, code):
        self.ensure_one()
        now = fields.Datetime.now()
        if not self.active or not self.pairing_hash or not self.pairing_expires_at:
            return False
        if now > self.pairing_expires_at or self.pairing_failures >= 5:
            return False
        if not isinstance(code, str) or not hmac.compare_digest(digest(code), self.pairing_hash):
            self.pairing_failures += 1
            return False
        token = secrets.token_urlsafe(32)
        self.write({
            "token_hash": digest(token),
            "pairing_hash": False,
            "pairing_expires_at": False,
            "pairing_failures": 0,
        })
        return token

    def accept_reading(self, token, payload):
        self.ensure_one()
        if not self.active or not self.token_hash or not isinstance(token, str):
            raise AccessError(_("Scale is not paired."))
        if not hmac.compare_digest(digest(token), self.token_hash):
            raise AccessError(_("Invalid scale token."))
        try:
            sample_id = str(uuid.UUID(str(payload["sample_id"])))
            weight = float(payload["weight"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError(_("Invalid scale reading.")) from exc
        unit = payload.get("unit")
        if unit not in ("lb", "kg") or not 0 < weight <= 100000:
            raise ValidationError(_("Unsupported unit or weight."))
        plu = payload.get("plu")
        if plu is not None and (not isinstance(plu, str) or len(plu) > 32):
            raise ValidationError(_("Invalid PLU."))
        if self.env["pos.scale.reading"].search_count([
            ("device_id", "=", self.id), ("sample_id", "=", sample_id)
        ]):
            raise ValidationError(_("Duplicate scale sample."))
        reading = self.env["pos.scale.reading"].create({
            "device_id": self.id,
            "sample_id": sample_id,
            "weight": weight,
            "unit": unit,
            "plu": plu or False,
        })
        self.last_reading_id = reading.id
        return reading

    @api.model
    def read_for_pos(self, config_id, product_id):
        if not self.env.user.has_group("point_of_sale.group_pos_user"):
            raise AccessError(_("POS access is required."))
        config = self.env["pos.config"].browse(int(config_id)).exists()
        if not config or not config.scale_device_id:
            raise ValidationError(_("Configure a scale on this POS first."))
        if config.company_id not in self.env.companies or config.scale_device_id.company_id != config.company_id:
            raise AccessError(_("This scale is not assigned to your POS company."))
        product = self.env["product.product"].browse(int(product_id)).exists()
        if not product or not product.product_tmpl_id.to_weight:
            raise ValidationError(_("Select a product sold by weight."))
        device = config.scale_device_id.sudo()
        reading = device.last_reading_id
        if not reading or (fields.Datetime.now() - reading.create_date).total_seconds() > 5:
            raise ValidationError(_("No fresh stable reading. Place the item on the scale."))
        if device.consumed_sample_id == reading.sample_id:
            raise ValidationError(_("This reading was already used. Wait for a new reading."))
        plu = product.product_tmpl_id.scale_plu
        if reading.plu and plu and reading.plu != plu:
            raise ValidationError(_("Scale PLU does not match the selected product."))
        source_uom = self.env.ref(
            "uom.product_uom_lb" if reading.unit == "lb" else "uom.product_uom_kgm"
        )
        source_root = source_uom
        target_root = product.uom_id
        while source_root.relative_uom_id:
            source_root = source_root.relative_uom_id
        while target_root.relative_uom_id:
            target_root = target_root.relative_uom_id
        if source_root != target_root:
            raise ValidationError(_("Product unit must be a weight unit."))
        quantity = source_uom._compute_quantity(reading.weight, product.uom_id, round=False)
        if quantity <= 0:
            raise ValidationError(_("Invalid converted quantity."))
        self.env.cr.execute(
            "UPDATE pos_scale_device SET consumed_sample_id = %s "
            "WHERE id = %s AND consumed_sample_id IS DISTINCT FROM %s",
            (reading.sample_id, device.id, reading.sample_id),
        )
        if self.env.cr.rowcount != 1:
            raise ValidationError(_("This reading was already used. Wait for a new reading."))
        reading.write({
            "consumed_at": fields.Datetime.now(),
            "consumed_pos_config_id": config.id,
            "consumed_product_id": product.id,
            "consumed_user_id": self.env.user.id,
        })
        return {
            "quantity": quantity,
            "unit": product.uom_id.name,
            "sample_id": reading.sample_id,
            "weight": reading.weight,
            "source_unit": reading.unit,
        }


class ScaleReading(models.Model):
    _name = "pos.scale.reading"
    _description = "Audited POS scale reading"
    _order = "create_date desc"

    device_id = fields.Many2one("pos.scale.device", required=True, ondelete="cascade", index=True)
    sample_id = fields.Char(required=True, index=True)
    weight = fields.Float(required=True)
    consumed_at = fields.Datetime(readonly=True)
    consumed_pos_config_id = fields.Many2one("pos.config", readonly=True)
    consumed_product_id = fields.Many2one("product.product", readonly=True)
    consumed_user_id = fields.Many2one("res.users", readonly=True)
    unit = fields.Selection([("lb", "lb"), ("kg", "kg")], required=True)
    plu = fields.Char()

    _unique_device_sample = models.Constraint(
        "unique(device_id, sample_id)", "Scale sample was already received."
    )


class PosConfig(models.Model):
    _inherit = "pos.config"

    scale_device_id = fields.Many2one("pos.scale.device", string="Scale device")


class ProductTemplate(models.Model):
    _inherit = "product.template"

    scale_plu = fields.Char(string="Scale PLU", help="Optional PLU sent by the scale gateway.")
