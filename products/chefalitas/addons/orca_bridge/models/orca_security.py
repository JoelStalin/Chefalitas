from odoo import _, api, models
from odoo.exceptions import AccessError

DEV_GROUP = "orca_bridge.group_orca_dev_admin"


class IrActionsServer(models.Model):
    """Executable Python in server actions is code running on the server: only the ORCA Dev Admin group
    (and the superuser) may create or change it. Other administrators keep managing views and reports."""

    _inherit = "ir.actions.server"

    def _check_orca_code_permission(self, vals_list):
        if self.env.su or self.env.user.has_group(DEV_GROUP):
            return
        if any(v.get("state") == "code" or "code" in v for v in vals_list):
            raise AccessError(_("Only the ORCA Dev Admin group may create or change Python code in server actions."))

    @api.model_create_multi
    def create(self, vals_list):
        self._check_orca_code_permission(vals_list)
        return super().create(vals_list)

    def write(self, vals):
        self._check_orca_code_permission([vals])
        return super().write(vals)
