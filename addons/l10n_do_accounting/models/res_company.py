from odoo import fields, models, _


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_do_dgii_start_date = fields.Date(
        string="Fecha de Inicio de Actividades",
        help="Fecha en la que la empresa inició sus operaciones ante la DGII."
    )

    l10n_do_ecf_issuer = fields.Boolean(
        string="Es emisor de e-CF",
        help="Cuando está activado, la empresa puede emitir comprobantes fiscales electrónicos (e-CF)."
    )

    l10n_do_ecf_deferred_submissions = fields.Boolean(
        string="Emisión Diferida",
        help="Indica si la empresa tiene autorización para emitir e-CF de forma diferida, por ejemplo, con dispositivos móviles fuera de línea (Handheld)."
    )

    def _localization_use_documents(self):
        """La localización dominicana usa documentos fiscales (NCF)."""
        self.ensure_one()
        return (
            True
            if self.country_id == self.env.ref("base.do")
            else super()._localization_use_documents()
        )
