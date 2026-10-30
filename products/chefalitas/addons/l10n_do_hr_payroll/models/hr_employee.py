from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class HrEmployee(models.Model):
    _inherit = "hr.employee"

    l10n_do_identification_type = fields.Selection(
        [
            ("cedula", "Cédula de Identidad"),
            ("rnc", "RNC"),
            ("passport", "Pasaporte"),
        ],
        string="Tipo de Identificación Fiscal",
        default="cedula",
        tracking=True,
        help="Tipo de documento para reportes de la TSS y formulario IR-4 ante la DGII.",
    )

    l10n_do_identification_id = fields.Char(
        string="Cédula / RNC",
        size=11,
        tracking=True,
        help="Cédula dominicana (11 dígitos sin guiones) o RNC.",
    )

    l10n_do_nss = fields.Char(
        string="No. Seguridad Social (NSS)",
        size=15,
        tracking=True,
        help="Número de afiliación del colaborador en la Tesorería de la Seguridad Social (TSS).",
    )

    l10n_do_is_exempt_isr = fields.Boolean(
        string="Exento de Retención ISR",
        default=False,
        tracking=True,
        help="Indica si el empleado cuenta con una exención legal expresa de retención de renta.",
    )

    l10n_do_has_other_income = fields.Boolean(
        string="Declara otros ingresos (IR-13)",
        default=False,
        help="Marcar si el colaborador recibe ingresos de más de un empleador y ha seleccionado esta empresa como agente único de retención.",
    )

    l10n_do_salary_payment_frequency = fields.Selection(
        [
            ("monthly", "Mensual"),
            ("biweekly", "Quincenal"),
            ("weekly", "Semanal"),
        ],
        string="Frecuencia de Pago",
        default="monthly",
        help="Frecuencia con la que se procesa la nómina del empleado.",
    )

    @api.constrains("l10n_do_identification_type", "l10n_do_identification_id")
    def _check_dominican_identification(self):
        for rec in self:
            if rec.l10n_do_identification_type == "cedula" and rec.l10n_do_identification_id:
                clean = rec.l10n_do_identification_id.replace("-", "").strip()
                if not clean.isdigit() or len(clean) != 11:
                    raise ValidationError(_("La cédula dominicana debe contener exactamente 11 dígitos numéricos."))