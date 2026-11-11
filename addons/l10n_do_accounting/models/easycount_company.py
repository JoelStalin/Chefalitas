from datetime import datetime, timedelta, timezone
import hashlib
from xml.sax.saxutils import escape

import odoo
from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .easycount_client import AUTH_OAUTH2, AUTH_TOKEN, EasyCountClient, EasyCountError

DR_TZ = timezone(timedelta(hours=-4))

# Tokens/URLs that select the built-in test emulator (only in the TesteCF environment).
TEST_TOKEN_PREFIXES = ("TEST-", "MODO-PRUEBA", "SANDBOX-")
TEST_URL_SCHEME = "emulador://"


class EasyCountLocalTestEmulator:
    """Built-in test-mode emulator ('Modo Prueba' / TesteCF) for EasyCount e-CF.

    Generates sequential test e-NCFs (E31..E47), 6-character DGII security codes,
    signed test XMLs, and QR stamps locally without transmitting anything to live DGII.
    Same interface as ``EasyCountClient``.
    """

    def __init__(self, company):
        self.company = company
        self.env = company.env

    def health(self):
        return {
            "service": "EasyCount (Modo Prueba)",
            "ok": True,
            "rnc": self.company.vat or "",
            "dgii_env": "TesteCF",
            "emulated": True,
            "auth_modes": [AUTH_TOKEN],
            "supported_types": ["31", "32", "33", "34", "41", "43", "44", "45", "46", "47"],
        }

    def get_credentials(self):
        return {
            "configured": True,
            "rnc": self.company.vat or "",
            "signer": "empresa",
            "cert_subject": f"CN={self.company.name} (CERTIFICADO DE PRUEBA TesteCF)",
            "cert_serial": f"TEST-{self.company.vat or 'ECF'}-2026",
            "cert_not_after": "2028-12-31T23:59:59Z",
            "portal_password": True,
        }

    def upload_credentials(self, payload):
        return self.get_credentials()

    def heartbeat(self, payload):
        return {"ok": True, "emulated": True, "is_blocked": False, "is_free_plan": True, "rnc": self.company.vat or ""}

    def _sequence_info(self, prefix):
        return {"e_cf_type": prefix, "active": True, "emulated": True}

    def get_sequences(self):
        types = self.health()["supported_types"]
        return {"items": [self._sequence_info(f"E{t}") for t in types], "emulated": True}

    def validate_sequence(self, e_cf_type=None):
        if not e_cf_type:
            return self.get_sequences()
        raw = e_cf_type.strip().upper()
        return self._sequence_info(raw if raw.startswith("E") else f"E{raw}")

    def allocate_encf(self, e_cf_type: str) -> str:
        raw = (e_cf_type or "E32").strip().upper()
        prefix = raw if raw.startswith("E") else f"E{raw}"
        seq_code = f"l10n_do.easycount.test.{prefix}.{self.company.id}"
        IrSeq = self.env["ir.sequence"].sudo()
        seq = IrSeq.search([("code", "=", seq_code)], limit=1)
        if not seq:
            seq = IrSeq.create({
                "name": f"EasyCount Modo Prueba {prefix} ({self.company.name})",
                "code": seq_code,
                "prefix": "",
                "padding": 10,
                "number_next": 1,
                "number_increment": 1,
                "company_id": self.company.id,
            })

        # Ensure next number is strictly greater than any existing e-NCF of this prefix in account_move
        self.env.cr.execute(
            """
            SELECT COALESCE(MAX(SUBSTRING(l10n_do_fiscal_number FROM 4)::bigint), 0)
            FROM account_move
            WHERE company_id = %s
              AND l10n_do_fiscal_number ~ %s
            """,
            (self.company.id, f"^{prefix}[0-9]{{10}}$"),
        )
        max_used = int((self.env.cr.fetchone() or [0])[0] or 0)
        if seq.number_next <= max_used:
            seq.write({"number_next": max_used + 1})

        num_str = seq.next_by_id()
        return f"{prefix}{int(num_str):010d}"

    def issue(self, payload: dict) -> dict:
        raw_type = str(payload.get("eCfType") or "E32").strip().upper()
        prefix = raw_type if raw_type.startswith("E") else f"E{raw_type}"
        tipo = prefix[1:]
        encf = payload.get("encf") or self.allocate_encf(prefix)
        issue_date = str(payload.get("issueDate") or fields.Date.context_today(self.company))
        total_amount = payload.get("totalAmount") or 0.0
        buyer_rnc = payload.get("buyerRnc") or ""
        buyer_name = payload.get("buyerName") or "CONSUMIDOR FINAL"

        now_dr = datetime.now(DR_TZ)
        sign_stamp = now_dr.strftime("%d-%m-%Y %H:%M:%S")
        seed = f"{self.company.vat}:{encf}:{issue_date}:{total_amount}:{sign_stamp}"
        sec_code = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:6].upper()

        xml_lines = []
        for idx, ln in enumerate(payload.get("lines") or [], start=1):
            desc = escape(str(ln.get("description") or "Item")[:160])
            qty = ln.get("quantity", 1)
            price = ln.get("unitPrice", 0)
            xml_lines.append(
                f"<Item><NumeroLinea>{idx}</NumeroLinea><NombreItem>{desc}</NombreItem>"
                f"<CantidadItem>{qty}</CantidadItem><PrecioUnitarioItem>{price}</PrecioUnitarioItem></Item>"
            )

        xml_str = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<ECF>"
            "<Encabezado>"
            "<Version>1.0</Version>"
            f"<IdDoc><TipoeCF>{escape(tipo)}</TipoeCF><eNCF>{escape(encf)}</eNCF></IdDoc>"
            f"<Emisor><RNCEmisor>{escape(str(self.company.vat or ''))}</RNCEmisor>"
            f"<RazonSocialEmisor>{escape(str(self.company.name or ''))}</RazonSocialEmisor>"
            f"<FechaEmision>{escape(issue_date)}</FechaEmision></Emisor>"
            f"<Comprador><RNCComprador>{escape(str(buyer_rnc))}</RNCComprador>"
            f"<RazonSocialComprador>{escape(str(buyer_name))}</RazonSocialComprador></Comprador>"
            f"<Totales><MontoTotal>{total_amount}</MontoTotal></Totales>"
            "</Encabezado>"
            f"<DetallesItems>{''.join(xml_lines)}</DetallesItems>"
            f"<FechaHoraFirma>{sign_stamp}</FechaHoraFirma>"
            f"<Signature><SignatureValue>{sec_code}==MODO_PRUEBA_EASYCOUNT==</SignatureValue></Signature>"
            "</ECF>"
        )

        return {
            "encf": encf,
            "trackId": f"TEST-{encf}-{sec_code}",
            "status": "Aceptado",
            "accepted": True,
            "messages": [
                {
                    "codigo": "0",
                    "valor": "MODO PRUEBA EASYCOUNT (TesteCF): Comprobante electrónico de prueba generado localmente (sin envío a DGII).",
                }
            ],
            "securityCode": sec_code,
            "signedAt": sign_stamp,
            "emulated": True,
            "xml": xml_str,
        }

    def status(self, encf: str) -> dict:
        return {
            "encf": encf,
            "status": "Aceptado",
            "accepted": True,
            "emulated": True,
        }


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

    def _l10n_do_easycount_uses_emulator(self):
        """True only in TesteCF with a test token (TEST-/MODO-PRUEBA/SANDBOX-) or an emulador:// URL."""
        self.ensure_one()
        if self.l10n_do_ecf_service_env != "TesteCF":
            return False
        token = (self.sudo().l10n_do_easycount_token or "").strip().upper()
        url = (self.l10n_do_easycount_url or "").strip().lower()
        return token.startswith(TEST_TOKEN_PREFIXES) or url.startswith(TEST_URL_SCHEME) or "modo-prueba" in url

    def _l10n_do_easycount_client(self):
        self.ensure_one()
        if self._l10n_do_easycount_uses_emulator():
            return EasyCountLocalTestEmulator(self)
        try:
            return EasyCountClient(
                self.l10n_do_easycount_url, self.sudo().l10n_do_easycount_token,
                auth_mode=self.l10n_do_easycount_auth_mode,
            )
        except EasyCountError as exc:
            raise UserError(_("Configuracion de EasyCount incompleta: %s", exc)) from exc

    def _l10n_do_easycount_send_heartbeat(self):
        """Report this Odoo to EasyCount and store the plan/payment block flags it returns."""
        self.ensure_one()
        if not self.l10n_do_easycount_enabled:
            return False
        client = self._l10n_do_easycount_client()
        payload = {
            "databaseName": self.env.cr.dbname,
            "odooVersion": getattr(odoo.release, "version", "20.0"),
            "tunnelUrl": self.l10n_do_easycount_tunnel_url or "",
            "odooUrl": self.env["ir.config_parameter"].sudo().get_param("web.base.url", ""),
            "modules": ["l10n_do_accounting", "pos_system"],
        }
        try:
            res = client.heartbeat(payload)
        except Exception:
            self.sudo().write({
                "l10n_do_easycount_is_connected": False,
                "l10n_do_easycount_last_heartbeat": fields.Datetime.now(),
            })
            raise
        self.sudo().write({
            "l10n_do_easycount_is_connected": True,
            "l10n_do_easycount_is_blocked": bool(res.get("is_blocked")),
            "l10n_do_easycount_block_reason": res.get("block_reason"),
            "l10n_do_easycount_last_heartbeat": fields.Datetime.now(),
        })
        return res

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
    _inherit = "res.config.settings"

    l10n_do_easycount_enabled = fields.Boolean(related="company_id.l10n_do_easycount_enabled", readonly=False)
    l10n_do_easycount_url = fields.Char(related="company_id.l10n_do_easycount_url", readonly=False)
    l10n_do_easycount_auth_mode = fields.Selection(related="company_id.l10n_do_easycount_auth_mode", readonly=False)
    l10n_do_easycount_token = fields.Char(related="company_id.l10n_do_easycount_token", readonly=False)
    l10n_do_ecf_service_env = fields.Selection(related="company_id.l10n_do_ecf_service_env", readonly=False)
    l10n_do_easycount_is_blocked = fields.Boolean(related="company_id.l10n_do_easycount_is_blocked", readonly=True)
    l10n_do_easycount_block_reason = fields.Char(related="company_id.l10n_do_easycount_block_reason", readonly=True)
    l10n_do_easycount_is_connected = fields.Boolean(related="company_id.l10n_do_easycount_is_connected", readonly=True)
    l10n_do_easycount_last_heartbeat = fields.Datetime(related="company_id.l10n_do_easycount_last_heartbeat", readonly=True)
    l10n_do_easycount_tunnel_url = fields.Char(related="company_id.l10n_do_easycount_tunnel_url", readonly=False)

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

    def action_l10n_do_easycount_send_heartbeat(self):
        self.ensure_one()
        res = self.company_id._l10n_do_easycount_send_heartbeat()
        if not res:
            raise UserError(_("Active primero la emision de e-CF con EasyCount."))
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
