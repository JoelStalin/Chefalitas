from datetime import date

from odoo import _, models
from odoo.exceptions import UserError

# Norma General 02-2026 (DGII, 16-09-2026): the ITBIS withholdings of Norma General 02-05 are
# not applied when, jointly, the supplier is a legal entity (persona juridica) authorised as
# electronic issuer and the operation is invoiced with an e-CF. Withholdings to individuals
# (personas fisicas) and under other provisions still apply.
NORMA_02_2026_DATE = date(2026, 9, 16)
NORMA_02_05_TAG = "N02-05"


class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_do_norma_02_2026_applies(self):
        """True when an N02-05 ITBIS withholding must not be applied to this vendor bill."""
        self.ensure_one()
        partner = self.commercial_partner_id
        vat = "".join(ch for ch in (partner.vat or "") if ch.isdigit())
        ncf_type = str(self.l10n_latam_document_type_id.l10n_do_ncf_type or "")
        return bool(
            self.country_code == "DO"
            and self.move_type in ("in_invoice", "in_refund")
            and (self.invoice_date or self.date) >= NORMA_02_2026_DATE
            and len(vat) == 9  # RNC de persona juridica (cedula = 11 digitos)
            and ncf_type.startswith("e-")
        )

    def _l10n_do_norma_02_05_withholding_taxes(self):
        taxes = self.invoice_line_ids.tax_ids.flatten_taxes_hierarchy()
        return taxes.filtered(
            lambda t: t.amount < 0 and NORMA_02_05_TAG in f"{t.name or ''} {t.description or ''}"
        )

    def _post(self, soft=True):
        for move in self.filtered(lambda m: m.is_purchase_document()):
            if move._l10n_do_norma_02_2026_applies():
                withholdings = move._l10n_do_norma_02_05_withholding_taxes()
                if withholdings:
                    raise UserError(_(
                        "Norma General 02-2026 (DGII): desde el 16-09-2026 no se aplica la retencion "
                        "de ITBIS de la Norma 02-05 a %(partner)s, persona juridica emisora "
                        "electronica que factura con e-CF (%(ncf)s). Quite: %(taxes)s.",
                        partner=move.commercial_partner_id.display_name,
                        ncf=move.l10n_do_fiscal_number or move.l10n_latam_document_type_id.doc_code_prefix,
                        taxes=", ".join(withholdings.mapped("name")),
                    ))
        return super()._post(soft)
