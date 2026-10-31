from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .easycount_client import AUTH_OAUTH2, AUTH_TOKEN, EasyCountClient, EasyCountError


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_do_easycount_enabled = fields.Boolean(
        string="Emitir e-CF con EasyCount",
        help="Los e-NCF y la transmision a DGII los realiza el servicio EasyCount.",
    )
    l10n_do_easycount_url = fields.Char(
        string="URL de EasyCount", default="https://api.getupsoft.com.do",
        help="Servidor EasyCount (desarrollo, staging o produccion).",
    )
    l10n_do_easycount_auth_mode = fields.Selection(
        [(AUTH_TOKEN, "Token de acceso"), (AUTH_OAUTH2, "OAuth 2.0 (proximamente)")],
        string="Autenticacion EasyCount", default=AUTH_TOKEN, required=True,
    )
    l10n_do_easycount_token = fields.Char(
        string="Token de EasyCount", groups="account.group_account_manager",
        help="Token Bearer entregado por el administrador de EasyCount para el RNC de esta empresa.",
    )
    l10n_do_ecf_service_env = fields.Selection(
        [("TesteCF", "TesteCF (pruebas DGII)"), ("CerteCF", "CerteCF (certificacion)"), ("eCF", "eCF (produccion)")],
        string="Ambiente DGII", default="TesteCF",
    )

    @api.constrains("l10n_do_easycount_auth_mode", "l10n_do_easycount_enabled")
    def _check_easycount_auth_mode(self):
        for company in self.filtered("l10n_do_easycount_enabled"):
            if company.l10n_do_easycount_auth_mode == AUTH_OAUTH2:
                raise UserError(_("OAuth 2.0 aun no esta disponible en EasyCount; use Token de acceso."))

    def _l10n_do_easycount_client(self):
        self.ensure_one()
        try:
            return EasyCountClient(
                self.l10n_do_easycount_url, self.sudo().l10n_do_easycount_token,
                auth_mode=self.l10n_do_easycount_auth_mode,
            )
        except EasyCountError as exc:
            raise UserError(_("Configuracion de EasyCount incompleta: %s", exc)) from exc


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_do_easycount_enabled = fields.Boolean(related="company_id.l10n_do_easycount_enabled", readonly=False)
    l10n_do_easycount_url = fields.Char(related="company_id.l10n_do_easycount_url", readonly=False)
    l10n_do_easycount_auth_mode = fields.Selection(related="company_id.l10n_do_easycount_auth_mode", readonly=False)
    l10n_do_easycount_token = fields.Char(related="company_id.l10n_do_easycount_token", readonly=False)
    l10n_do_ecf_service_env = fields.Selection(related="company_id.l10n_do_ecf_service_env", readonly=False)

    def action_l10n_do_easycount_credentials(self):
        self.ensure_one()
        return self.env["ir.actions.act_window"]._for_xml_id("l10n_do_accounting.action_l10n_do_easycount_credentials_wizard")

    def action_l10n_do_easycount_test_connection(self):
        self.ensure_one()
        client = self.company_id._l10n_do_easycount_client()
        try:
            info = client.health()
        except EasyCountError as exc:
            raise UserError(_("No se pudo validar la conexion con EasyCount: %s", exc)) from exc
        mode = _("EMULADOR DGII") if info.get("emulated") else info.get("dgii_env")
        return {
            "type": "ir.actions.client", "tag": "display_notification",
            "params": {"title": _("EasyCount"), "type": "success", "sticky": False,
                       "message": _("Conectado. RNC %(rnc)s, ambiente %(env)s.", rnc=info.get("rnc"), env=mode)},
        }
