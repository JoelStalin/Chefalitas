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
        string="URL de EasyCount", default="https://easycount.me",
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
    l10n_do_easycount_is_blocked = fields.Boolean(
        string="Servicio EasyCount Bloqueado",
        readonly=True,
        help="Indica si la empresa ha excedido su plan o tiene una mensualidad pendiente de pago en EasyCount.",
    )
    l10n_do_easycount_block_reason = fields.Char(
        string="Razón de Bloqueo EasyCount",
        readonly=True,
    )
    l10n_do_easycount_is_connected = fields.Boolean(
        string="EasyCount Conectado",
        readonly=True,
    )
    l10n_do_easycount_last_heartbeat = fields.Datetime(
        string="Último Heartbeat EasyCount",
        readonly=True,
    )
    l10n_do_easycount_tunnel_url = fields.Char(
        string="URL del Túnel Odoo",
        help="URL pública o túnel Cloudflare de esta instancia de Odoo para comunicación con EasyCount.",
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

    
    def _l10n_do_easycount_send_heartbeat(self):
        self.ensure_one()
        if not self.l10n_do_easycount_enabled:
            return False
        client = self._l10n_do_easycount_client()
        import odoo
        from odoo import fields as odoo_fields
        payload = {
            "databaseName": self.env.cr.dbname,
            "odooVersion": getattr(odoo.release, "version", "20.0"),
            "tunnelUrl": self.l10n_do_easycount_tunnel_url or "",
            "odooUrl": self.env["ir.config_parameter"].sudo().get_param("web.base.url", ""),
            "modules": ["l10n_do_accounting", "pos_system"],
        }
        try:
            res = client.heartbeat(payload)
            self.sudo().write({
                "l10n_do_easycount_is_connected": True,
                "l10n_do_easycount_is_blocked": bool(res.get("is_blocked")),
                "l10n_do_easycount_block_reason": res.get("block_reason"),
                "l10n_do_easycount_last_heartbeat": odoo_fields.Datetime.now(),
            })
            return res
        except Exception as exc:
            self.sudo().write({
                "l10n_do_easycount_is_connected": False,
                "l10n_do_easycount_last_heartbeat": odoo_fields.Datetime.now(),
            })
            raise

    def _l10n_do_easycount_client(self):
        self.ensure_one()
        try:
            return EasyCountClient(
                self.l10n_do_easycount_url, self.sudo().l10n_do_easycount_token,
                auth_mode=self.l10n_do_easycount_auth_mode,
            )
        except EasyCountError as exc:
            raise UserError(_("Configuracion de EasyCount incompleta: %s", exc)) from exc

    def _l10n_do_easycount_validate_sequences(self, e_cf_type=None, sync_journals=True):
        """Queries and validates active sequences in EasyCount and optionally syncs journal expiration dates."""
        self.ensure_one()
        client = self._l10n_do_easycount_client()
        try:
            if e_cf_type:
                info = client.validate_sequence(e_cf_type)
            else:
                info = client.get_sequences()
        except EasyCountError as exc:
            raise UserError(_("No se pudieron validar las secuencias activas en EasyCount: %s", exc)) from exc

        if sync_journals and isinstance(info, dict):
            items = [info] if e_cf_type else (info.get("items") or [])
            self._l10n_do_sync_easycount_journal_sequences(items)
        return info

    def _l10n_do_sync_easycount_journal_sequences(self, items):
        """Synchronizes active sequence expiration dates from EasyCount into fiscal journal document types."""
        self.ensure_one()
        journals = self.env["account.journal"].search([
            ("company_id", "=", self.id),
            ("type", "in", ("sale", "purchase")),
            ("l10n_latam_use_documents", "=", True),
        ])
        for journal in journals:
            if not journal.l10n_do_document_type_ids:
                journal._l10n_do_create_document_types()

        by_prefix = {
            (item.get("e_cf_type") or item.get("eCfType")): item
            for item in (items or [])
            if isinstance(item, dict) and (item.get("e_cf_type") or item.get("eCfType"))
        }
        if not by_prefix:
            return
        for jdoc in journals.mapped("l10n_do_document_type_ids"):
            prefix = jdoc.l10n_latam_document_type_id.doc_code_prefix or ""
            seq_item = by_prefix.get(prefix)
            expires_on = (seq_item or {}).get("expires_on") or (seq_item or {}).get("expiresOn")
            if seq_item and seq_item.get("active") and expires_on:
                jdoc.l10n_do_ncf_expiration_date = expires_on


class ResConfigSettings(models.TransientModel):
    l10n_do_easycount_is_blocked = fields.Boolean(related="company_id.l10n_do_easycount_is_blocked", readonly=True)
    l10n_do_easycount_block_reason = fields.Char(related="company_id.l10n_do_easycount_block_reason", readonly=True)
    l10n_do_easycount_is_connected = fields.Boolean(related="company_id.l10n_do_easycount_is_connected", readonly=True)
    l10n_do_easycount_last_heartbeat = fields.Datetime(related="company_id.l10n_do_easycount_last_heartbeat", readonly=True)
    l10n_do_easycount_tunnel_url = fields.Char(related="company_id.l10n_do_easycount_tunnel_url", readonly=False)

    def action_l10n_do_easycount_send_heartbeat(self):
        self.ensure_one()
        res = self.company_id._l10n_do_easycount_send_heartbeat()
        status_msg = _("Bloqueado") if res.get("is_blocked") else _("Activo (Sin Bloqueo)")
        if res.get("is_free_plan"):
            status_msg = _("Activo (Plan Gratuito)")
        return {
            "type": "ir.actions.client", "tag": "display_notification",
            "params": {
                "title": _("Heartbeat EasyCount"),
                "type": "success" if not res.get("is_blocked") else "warning",
                "sticky": False,
                "message": _("Sincronizado con EasyCount. Estado: %(st)s. RNC: %(rnc)s.", st=status_msg, rnc=res.get("rnc")),
            },
        }

    _inherit = "res.config.settings"

    l10n_do_easycount_enabled = fields.Boolean(related="company_id.l10n_do_easycount_enabled", readonly=False)
    l10n_do_easycount_url = fields.Char(related="company_id.l10n_do_easycount_url", readonly=False)
    l10n_do_easycount_auth_mode = fields.Selection(related="company_id.l10n_do_easycount_auth_mode", readonly=False)
    l10n_do_easycount_token = fields.Char(related="company_id.l10n_do_easycount_token", readonly=False)
    l10n_do_easycount_is_blocked = fields.Boolean(
        string="Servicio EasyCount Bloqueado",
        readonly=True,
        help="Indica si la empresa ha excedido su plan o tiene una mensualidad pendiente de pago en EasyCount.",
    )
    l10n_do_easycount_block_reason = fields.Char(
        string="Razón de Bloqueo EasyCount",
        readonly=True,
    )
    l10n_do_easycount_is_connected = fields.Boolean(
        string="EasyCount Conectado",
        readonly=True,
    )
    l10n_do_easycount_last_heartbeat = fields.Datetime(
        string="Último Heartbeat EasyCount",
        readonly=True,
    )
    l10n_do_easycount_tunnel_url = fields.Char(
        string="URL del Túnel Odoo",
        help="URL pública o túnel Cloudflare de esta instancia de Odoo para comunicación con EasyCount.",
    )

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

    def action_l10n_do_easycount_validate_sequences(self):
        self.ensure_one()
        info = self.company_id._l10n_do_easycount_validate_sequences(sync_journals=True)
        items = info.get("items") or []
        active = [i for i in items if i.get("active")]
        inactive = [i for i in items if not i.get("active")]
        if not active:
            reason = (
                "; ".join(i.get("reason") for i in inactive if i.get("reason"))
                or _("No hay secuencias activas configuradas en EasyCount para este RNC.")
            )
            raise UserError(_("EasyCount: %s", reason))
        summary = ", ".join(
            f"{i.get('e_cf_type') or i.get('eCfType')} ({i.get('next_encf') or i.get('next_number')})"
            for i in active
        )
        return {
            "type": "ir.actions.client", "tag": "display_notification",
            "params": {
                "title": _("Secuencias EasyCount"),
                "type": "success",
                "sticky": False,
                "message": _(
                    "Secuencias activas validadas y sincronizadas (%(n)s): %(s)s",
                    n=len(active),
                    s=summary,
                ),
            },
        }


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_post(self):
        return super().action_post()
