from odoo import models, fields, api, _
from odoo.exceptions import AccessError


class Partner(models.Model):
    _inherit = "res.partner"

    def _get_l10n_do_dgii_payer_types_selection(self):
        return [
            ("taxpayer", _("Contribuyente Fiscal")),
            ("non_payer", _("No Contribuyente")),
            ("nonprofit", _("Entidad sin Fines de Lucro")),
            ("special", _("Régimen Especial")),
            ("governmental", _("Gubernamental")),
            ("foreigner", _("Extranjero")),
        ]

    def _get_l10n_do_expense_type(self):
        return [
            ("01", _("01 - Personal")),
            ("02", _("02 - Trabajo, Suministros y Servicios")),
            ("03", _("03 - Arrendamiento")),
            ("04", _("04 - Activos Fijos")),
            ("05", _("05 - Representación")),
            ("06", _("06 - Deducciones Admitidas")),
            ("07", _("07 - Gastos Financieros")),
            ("08", _("08 - Gastos Extraordinarios")),
            ("09", _("09 - Costo y Gastos de Ventas")),
            ("10", _("10 - Adquisición de Activos")),
            ("11", _("11 - Gastos de Seguros")),
        ]

    l10n_do_dgii_tax_payer_type = fields.Selection(
        selection="_get_l10n_do_dgii_payer_types_selection",
        compute="_compute_l10n_do_dgii_payer_type",
        inverse="_inverse_l10n_do_dgii_tax_payer_type",
        string="Tipo de Contribuyente",
        index=True,
        store=True,
    )

    l10n_do_expense_type = fields.Selection(
        selection="_get_l10n_do_expense_type",
        string="Tipo de Gasto",
        store=True,
    )

    country_id = fields.Many2one(
        default=lambda self: self.env.ref("base.do")
        if self.env.user.company_id.country_id == self.env.ref("base.do")
        else False
    )

    def _check_l10n_do_fiscal_fields(self, vals):
        if not self or self.parent_id:
            return

        fiscal_fields = [
            f for f in ["name", "vat", "country_id"] if f in vals
        ]

        if (
            fiscal_fields
            and not self.env.user.has_group("l10n_do_accounting.group_l10n_do_edit_fiscal_partner")
            and self.env["account.move"]
            .sudo()
            .search([
                ("l10n_latam_use_documents", "=", True),
                ("country_code", "=", "DO"),
                ("commercial_partner_id", "=", self.id),
                ("state", "=", "posted"),
            ], limit=1)
        ):
            raise AccessError(_(
                "No tienes permisos para modificar %s luego de emitir comprobantes fiscales."
            ) % (", ".join(self._fields[f].string for f in fiscal_fields)))

    def write(self, vals):
        res = super().write(vals)
        self._check_l10n_do_fiscal_fields(vals)
        return res

    @api.depends("vat", "country_id", "name")
    def _compute_l10n_do_dgii_payer_type(self):
        for partner in self:
            vat = partner.vat or partner.name or ""
            vat_len = len(vat)
            upper_name = partner.name.upper() if partner.name else ""
            is_dominican = partner.country_code == "DO"

            if not is_dominican:
                partner.l10n_do_dgii_tax_payer_type = "foreigner"
                continue

            if not vat.isdigit():
                partner.l10n_do_dgii_tax_payer_type = "non_payer"
                continue

            if vat_len == 11:
                partner.l10n_do_dgii_tax_payer_type = "non_payer"
            elif vat_len == 9:
                if "MINISTERIO" in upper_name and not vat.startswith("4"):
                    partner.l10n_do_dgii_tax_payer_type = "governmental"
                elif "ZONA FRANCA" in upper_name:
                    partner.l10n_do_dgii_tax_payer_type = "special"
                elif "IGLESIA" in upper_name or ("MINISTERIO" in upper_name and vat.startswith("4")):
                    partner.l10n_do_dgii_tax_payer_type = "special"
                elif not vat.startswith("4"):
                    partner.l10n_do_dgii_tax_payer_type = "taxpayer"
                else:
                    partner.l10n_do_dgii_tax_payer_type = "nonprofit"
            else:
                partner.l10n_do_dgii_tax_payer_type = "non_payer"

    def _inverse_l10n_do_dgii_tax_payer_type(self):
        for partner in self:
            partner.l10n_do_dgii_tax_payer_type = partner.l10n_do_dgii_tax_payer_type
