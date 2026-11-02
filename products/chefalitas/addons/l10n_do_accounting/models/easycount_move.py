import logging
import re

from odoo import _, fields, models
from odoo.tools import BinaryBytes
from odoo.exceptions import UserError

from .easycount_client import EasyCountError
from .easycount_payload import build_issue_payload

_logger = logging.getLogger(__name__)
ACCEPTED = {"Aceptado", "Aceptado Condicional", "En Proceso"}
# e-CF the company issues as BUYER on vendor bills: compras (informal supplier), gastos menores,
# pagos al exterior. Other vendor bills carry the supplier's own NCF and are not sent.
BUYER_ISSUED_TYPES = ("E41", "E43", "E47")


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_do_easycount_track_id = fields.Char("TrackId DGII (EasyCount)", copy=False, readonly=True)
    l10n_do_easycount_status = fields.Char("Estado DGII", copy=False, readonly=True)
    l10n_do_easycount_messages = fields.Text("Mensajes DGII", copy=False, readonly=True)
    l10n_do_easycount_emulated = fields.Boolean("Emitido en emulador", copy=False, readonly=True)
    l10n_do_easycount_pending = fields.Boolean("Pendiente de envio", copy=False, readonly=True)

    def _l10n_do_numbered_by_easycount(self):
        """e-CF whose e-NCF EasyCount assigns: issued by the company (sales, or E41/E43/E47 bills)."""
        self.ensure_one()
        prefix = self.l10n_latam_document_type_id.doc_code_prefix or ""
        return bool(
            self.country_code == "DO"
            and self.company_id.l10n_do_easycount_enabled
            and prefix.startswith("E")
            and (self.move_type in ("out_invoice", "out_refund")
                 or (self.move_type == "in_invoice" and prefix in BUYER_ISSUED_TYPES))
        )

    def _l10n_do_uses_easycount(self):
        self.ensure_one()
        doc = self.l10n_latam_document_type_id
        prefix = (doc.doc_code_prefix or "") if doc else ""
        issued_by_company = self.move_type in ("out_invoice", "out_refund") or (
            self.move_type == "in_invoice" and prefix in BUYER_ISSUED_TYPES
        )
        return bool(
            self.country_code == "DO"
            and issued_by_company
            and self.company_id.l10n_do_easycount_enabled
            and prefix.startswith("E")
            and not self.l10n_do_easycount_track_id
        )

    def _post(self, soft=True):
        todo = self.filtered(lambda m: m.state == "draft" and m._l10n_do_uses_easycount())
        for move in todo:
            if not move.l10n_do_fiscal_number:
                client = move.company_id._l10n_do_easycount_client()
                try:
                    encf = client.allocate_encf(move.l10n_latam_document_type_id.doc_code_prefix)
                except EasyCountError as exc:
                    raise UserError(_("EasyCount no pudo asignar el e-NCF: %s", exc)) from exc
                move.l10n_do_fiscal_number = encf
                if move.move_type in ("out_invoice", "out_refund"):
                    move.name = encf
                else:
                    # vendor bills keep their internal journal name; the e-NCF is the fiscal number
                    move.l10n_latam_document_number = encf
        posted = super()._post(soft)
        for move in todo.filtered(lambda m: m.state == "posted"):
            move._l10n_do_easycount_issue()
        return posted

    def _l10n_do_easycount_issue(self):
        self.ensure_one()
        client = self.company_id._l10n_do_easycount_client()
        try:
            result = client.issue(build_issue_payload(self, self.l10n_do_fiscal_number))
        except EasyCountError as exc:
            if self.company_id.l10n_do_ecf_deferred_submissions and exc.status is None:
                self.l10n_do_easycount_pending = True
                _logger.warning("EasyCount no disponible; %s queda pendiente: %s", self.name, exc)
                return
            raise UserError(_("EasyCount no pudo emitir %(n)s: %(e)s", n=self.name, e=exc)) from exc
        messages = "\n".join(f"[{m.get('codigo')}] {m.get('valor')}" for m in result.get("messages", []))
        if not result.get("accepted"):
            raise UserError(_("DGII rechazo %(n)s (%(s)s):\n%(m)s", n=self.name, s=result.get("status"), m=messages))
        vals = {
            "l10n_do_easycount_track_id": result.get("trackId"),
            "l10n_do_easycount_status": result.get("status"),
            "l10n_do_easycount_messages": messages,
            "l10n_do_easycount_emulated": bool(result.get("emulated")),
            "l10n_do_easycount_pending": False,
            "l10n_do_ecf_security_code": result.get("securityCode"),
            "l10n_do_ecf_sign_date": fields.Datetime.now(),
        }
        if result.get("xml"):
            signed = re.search(r"<FechaHoraFirma>([^<]+)</FechaHoraFirma>", result["xml"])
            if signed:
                vals["l10n_do_ecf_sign_stamp"] = signed.group(1).strip()
            vals["l10n_do_ecf_edi_file"] = BinaryBytes(
                result["xml"].encode(), f"{self.l10n_do_fiscal_number}.xml"
            )
            vals["l10n_do_ecf_edi_file_name"] = f"{self.l10n_do_fiscal_number}.xml"
        self.write(vals)

    def action_l10n_do_easycount_retry(self):
        for move in self.filtered(lambda m: m.l10n_do_easycount_pending and m.state == "posted"):
            move._l10n_do_easycount_issue()
