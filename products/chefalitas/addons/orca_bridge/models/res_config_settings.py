from odoo import api, fields, models
from odoo.exceptions import AccessError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    orca_bridge_url = fields.Char("URL de ORCA", config_parameter="orca_bridge.url",
                                  help="Ej. https://orca.getupsoft.com")
    orca_bridge_client_id = fields.Char("Client ID", config_parameter="orca_bridge.client_id",
                                        help="Conector OAuth registrado en ORCA > Configuracion > su compania")
    orca_bridge_client_secret = fields.Char("Client secret", config_parameter="orca_bridge.client_secret",
                                            groups="base.group_system")
    orca_bridge_push_events = fields.Boolean("Notificar cambios a ORCA", config_parameter="orca_bridge.push_events")
    orca_bridge_redirect_uri = fields.Char("URL de retorno", compute="_compute_orca_bridge_status")
    orca_bridge_connected = fields.Boolean("Conectado a ORCA", compute="_compute_orca_bridge_status")
    orca_bridge_status = fields.Char("Estado de ORCA", compute="_compute_orca_bridge_status")

    @api.depends_context("uid")
    def _compute_orca_bridge_status(self):
        client = self.env["orca.bridge.client"]
        s = client._settings()
        connected = client._is_connected()
        status = (self.env._("Conectado a %(company)s como %(connection)s desde %(date)s",
                             company=s["company"], connection=s["connection"], date=s["connected_at"])
                  if connected else self.env._("No conectado"))
        for settings in self:
            settings.orca_bridge_redirect_uri = client._redirect_uri()
            settings.orca_bridge_connected = connected
            settings.orca_bridge_status = status

    def _check_orca_admin(self):
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(self.env._("Solo un administrador puede gestionar la conexion con ORCA."))

    def action_orca_bridge_connect(self):
        """Saves the settings and starts OAuth 2.0 in the browser (ORCA login + consent screen)."""
        self.ensure_one()
        self._check_orca_admin()
        self.set_values()
        return {"type": "ir.actions.act_url", "url": "/orca_bridge/oauth/start", "target": "self"}

    def action_orca_bridge_disconnect(self):
        self.ensure_one()
        self._check_orca_admin()
        self.env["orca.bridge.client"]._disconnect()
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_orca_bridge_test_connection(self):
        self.ensure_one()
        self._check_orca_admin()
        whoami = self.env["orca.bridge.client"]._request("GET", "/api/orca/odoo-bridge/whoami")
        ok = "events" in whoami.get("scopes", [])
        message = self.env._(
            "ORCA responde: %(client)s, compania %(company)s, permisos %(scopes)s.",
            client=whoami.get("client"), company=whoami.get("company"), scopes=", ".join(whoami.get("scopes", [])),
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": "ORCA", "message": message, "type": "success" if ok else "warning", "sticky": False},
        }
