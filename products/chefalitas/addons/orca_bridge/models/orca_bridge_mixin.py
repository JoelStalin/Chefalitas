from odoo import api, models


class OrcaBridgeMixin(models.AbstractModel):
    """Notify ORCA when records change (ids and field names only, never values)."""

    _name = "orca.bridge.mixin"
    _description = "ORCA change notifications"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env["orca.bridge.client"]._push_event(records, "create", {f for vals in vals_list for f in vals})
        return records

    def write(self, vals):
        result = super().write(vals)
        self.env["orca.bridge.client"]._push_event(self, "write", vals.keys())
        return result

    def unlink(self):
        self.env["orca.bridge.client"]._push_event(self, "unlink")
        return super().unlink()


class ResPartner(models.Model):
    _name = "res.partner"
    _inherit = ["res.partner", "orca.bridge.mixin"]


class AccountMove(models.Model):
    _name = "account.move"
    _inherit = ["account.move", "orca.bridge.mixin"]

    def _post(self, soft=True):
        posted = super()._post(soft)
        self.env["orca.bridge.client"]._push_event(posted, "post", ["state", "name"])
        return posted


class PosOrder(models.Model):
    _name = "pos.order"
    _inherit = ["pos.order", "orca.bridge.mixin"]


class StockPicking(models.Model):
    _name = "stock.picking"
    _inherit = ["stock.picking", "orca.bridge.mixin"]
