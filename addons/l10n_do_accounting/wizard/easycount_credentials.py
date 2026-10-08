import base64

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models.easycount_client import EasyCountError


class L10nDoEasyCountCredentialsWizard(models.TransientModel):
    """Uploads the company's DGII credentials to EasyCount: signing certificate (.p12) with its password and the
    password of the DGII certification portal. EasyCount validates and stores them encrypted; Odoo keeps nothing:
    the secrets are sent once and wiped from this transient record right after."""

    _name = "l10n_do.easycount.credentials.wizard"
    _description = "Credenciales DGII en EasyCount"

    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, readonly=True)
    company_vat = fields.Char(related="company_id.vat", string="RNC")
    p12_file = fields.Binary("Certificado digital (.p12/.pfx)", attachment=False)
    p12_filename = fields.Char()
    p12_password = fields.Char("Clave del certificado")
    portal_user = fields.Char("Usuario del portal de certificación", help="RNC/cédula con el que entra al portal.")
    portal_password = fields.Char(
        "Clave del portal de certificación",
        help="La del login propio de ecf.dgii.gov.do/certecf/portalcertificacion (no la de la OFV). "
             "Vacía: se conserva la que ya está en EasyCount.",
    )
    status_text = fields.Text("Estado en EasyCount", readonly=True)

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        company = self.env.company
        vals["portal_user"] = company.vat
        vals["status_text"] = self._status_text(company)
        return vals

    @api.model
    def _status_text(self, company):
        try:
            st = company._l10n_do_easycount_client().get_credentials()
        except (EasyCountError, UserError) as exc:
            return _("No se pudo consultar EasyCount: %s", exc)
        if not st.get("configured"):
            return _("Sin credenciales cargadas para el RNC %s.", st.get("rnc") or company.vat)
        signer = _("su representante autorizado") if st.get("signer") == "representante" else _("la empresa")
        return _(
            "Certificado de %(cn)s (%(serial)s), vence %(exp)s; firma %(signer)s.\nClave del portal: %(portal)s.",
            cn=st.get("cert_subject"), serial=st.get("cert_serial"), exp=str(st.get("cert_not_after") or "")[:10],
            signer=signer, portal=_("cargada") if st.get("portal_password") else _("no cargada"),
        )

    @staticmethod
    def _b64(value):
        if hasattr(value, "content"):  # Odoo 20 BinaryBytes
            value = value.content
        if isinstance(value, bytes):
            # binary widgets hand over base64 text; raw bytes (BinaryBytes) are encoded here
            try:
                base64.b64decode(value, validate=True)
                return value.decode()
            except ValueError:
                return base64.b64encode(value).decode()
        return value or ""

    def action_send(self):
        self.ensure_one()
        if not self.p12_file or not self.p12_password:
            raise UserError(_("Seleccione el certificado y escriba su clave."))
        company = self.company_id
        if not company.vat:
            raise UserError(_("La empresa no tiene RNC configurado."))
        payload = {
            "company_name": company.name,
            "p12_base64": self._b64(self.p12_file),
            "p12_password": self.p12_password,
            "portal_user": (self.portal_user or company.vat).strip(),
        }
        if self.portal_password:
            payload["portal_password"] = self.portal_password
        try:
            st = company._l10n_do_easycount_client().upload_credentials(payload)
        except EasyCountError as exc:
            raise UserError(_("EasyCount no aceptó las credenciales: %s", exc)) from exc
        finally:
            # never keep the secrets in Odoo, not even in this transient record
            self.write({"p12_file": False, "p12_password": False, "portal_password": False})
        return {
            "type": "ir.actions.client", "tag": "display_notification",
            "params": {"title": _("Credenciales DGII guardadas en EasyCount"), "type": "success", "sticky": True,
                       "message": _("Certificado de %(cn)s, vence %(exp)s.", cn=st.get("cert_subject"),
                                    exp=str(st.get("cert_not_after") or "")[:10]),
                       "next": {"type": "ir.actions.act_window_close"}},
        }
