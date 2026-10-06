from odoo import fields, models
from odoo.exceptions import AccessError
from odoo.http import request

API_KEY_SCOPE = "rpc"  # Odoo 20 JSON-2 API (/json/2/<model>/<method>)
API_KEY_NAME = "ORCA bridge"


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    orca_bridge_url = fields.Char("URL de ORCA", config_parameter="orca_bridge.url",
                                  help="Ej. https://orca.getupsoft.com")
    orca_bridge_token = fields.Char("Token de ORCA", config_parameter="orca_bridge.token",
                                    groups="base.group_system",
                                    help="Token que ORCA asigno a esta instancia (scope events)")
    orca_bridge_connection_id = fields.Char("Conexion en ORCA", config_parameter="orca_bridge.connection_id",
                                            help="Id de esta instancia en ORCA_ODOO_CONNECTIONS; por defecto la base de datos")
    orca_bridge_push_events = fields.Boolean("Notificar cambios a ORCA", config_parameter="orca_bridge.push_events")
    orca_bridge_api_key_count = fields.Integer("Claves API de ORCA", compute="_compute_orca_bridge_api_key_count")

    def _orca_bridge_user(self):
        return self.env.ref("orca_bridge.user_orca_bridge")

    def _compute_orca_bridge_api_key_count(self):
        count = self.env["res.users.apikeys"].sudo().search_count([
            ("user_id", "=", self._orca_bridge_user().id), ("scope", "=", API_KEY_SCOPE)])
        for settings in self:
            settings.orca_bridge_api_key_count = count

    def action_orca_bridge_test_connection(self):
        self.ensure_one()
        self.set_values()
        whoami = self.env["orca.bridge.client"]._request("GET", "/api/orca/odoo-bridge/whoami")
        connection = self.env["orca.bridge.client"]._settings()["connection"]
        allowed = "*" in whoami.get("connections", []) or connection in whoami.get("connections", [])
        ok = "events" in whoami.get("scopes", []) and allowed
        message = self.env._(
            "Cliente ORCA %(client)s, permisos %(scopes)s, conexion %(connection)s %(state)s.",
            client=whoami.get("client"), scopes=", ".join(whoami.get("scopes", [])), connection=connection,
            state=self.env._("autorizada") if ok else self.env._("NO autorizada para eventos"),
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": "ORCA", "message": message, "type": "success" if ok else "warning", "sticky": False},
        }

    def action_orca_bridge_generate_api_key(self):
        """(Re)generate the JSON-2 API key ORCA uses; previous ORCA keys are revoked. Shown once."""
        self.ensure_one()
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(self.env._("Only administrators can generate the ORCA API key."))
        user = self._orca_bridge_user()
        keys = self.env["res.users.apikeys"].with_user(user).sudo()
        keys.search([("user_id", "=", user.id), ("scope", "=", API_KEY_SCOPE)]).unlink()
        key = keys._generate(API_KEY_SCOPE, API_KEY_NAME, None)
        base_url = ((request and request.httprequest.url_root) or self.get_base_url()).rstrip("/")
        return {
            "type": "ir.actions.act_window",
            "res_model": "res.users.apikeys.show",
            "name": self.env._("Clave API para ORCA (copiela ahora)"),
            "views": [(False, "form")],
            "target": "new",
            "context": {"default_key": key, "default_scope": API_KEY_SCOPE, "default_base_url": base_url},
        }

    def action_orca_bridge_revoke_api_keys(self):
        self.ensure_one()
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(self.env._("Only administrators can revoke the ORCA API key."))
        user = self._orca_bridge_user()
        self.env["res.users.apikeys"].sudo().search([("user_id", "=", user.id), ("scope", "=", API_KEY_SCOPE)]).unlink()
        return True
