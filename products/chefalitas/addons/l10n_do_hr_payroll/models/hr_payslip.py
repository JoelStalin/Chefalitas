from decimal import Decimal
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from .l10n_do_payroll_calculator import calculate_dominican_payroll, DEFAULT_NATIONAL_MIN_WAGE

class L10nDoPayslip(models.Model):
    _name = "l10n_do.payslip"
    _description = "Recibo de Nómina Dominicana (TSS & DGII)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_to desc, id desc"

    name = fields.Char(string="Referencia", required=True, copy=False, default="/")
    employee_id = fields.Many2one("hr.employee", string="Colaborador", required=True, tracking=True)
    date_from = fields.Date(string="Desde", required=True, default=fields.Date.context_today)
    date_to = fields.Date(string="Hasta", required=True, default=fields.Date.context_today)
    state = fields.Selection([
        ("draft", "Borrador"),
        ("calculated", "Calculada"),
        ("posted", "Contabilizada / Pagada"),
        ("cancel", "Cancelada"),
    ], string="Estado", default="draft", tracking=True)

    company_id = fields.Many2one("res.company", string="Compañía", default=lambda self: self.env.company)
    currency_id = fields.Many2one("res.currency", string="Moneda", related="company_id.currency_id")

    # Salarios y Percepciones
    wage_base = fields.Monetary(string="Salario Base Ordinario", required=True, default=0.0, tracking=True)
    overtime_amount = fields.Monetary(string="Horas Extras", default=0.0)
    commissions_amount = fields.Monetary(string="Comisiones", default=0.0)
    gross_wage = fields.Monetary(string="Salario Bruto Cotizable", compute="_compute_totals", store=True)

    # Deducciones de Ley Empleado (TSS)
    sfs_employee = fields.Monetary(string="SFS Empleado (3.04%)", compute="_compute_totals", store=True)
    afp_employee = fields.Monetary(string="AFP Empleado (2.87%)", compute="_compute_totals", store=True)
    total_tss_employee = fields.Monetary(string="Total TSS Empleado (5.91%)", compute="_compute_totals", store=True)

    # Retención de Impuesto Sobre la Renta (DGII)
    taxable_base_isr = fields.Monetary(string="Base Imponible ISR", compute="_compute_totals", store=True)
    isr_retention = fields.Monetary(string="Retención ISR Asalariados (IR-3)", compute="_compute_totals", store=True)

    # Otras Deducciones
    other_deductions = fields.Monetary(string="Otras Deducciones (Préstamos/Avances)", default=0.0)
    total_deductions = fields.Monetary(string="Total Deducciones", compute="_compute_totals", store=True)
    net_wage = fields.Monetary(string="Salario Neto a Pagar", compute="_compute_totals", store=True)

    # Aportes Patronales (TSS & INFOTEP)
    sfs_employer = fields.Monetary(string="SFS Patronal (7.09%)", compute="_compute_totals", store=True)
    afp_employer = fields.Monetary(string="AFP Patronal (7.10%)", compute="_compute_totals", store=True)
    srl_employer = fields.Monetary(string="SRL Riesgos Laborales (1.20%)", compute="_compute_totals", store=True)
    infotep_employer = fields.Monetary(string="Aporte INFOTEP (1.00%)", compute="_compute_totals", store=True)
    total_employer_contributions = fields.Monetary(string="Total Aportes Patronales", compute="_compute_totals", store=True)
    total_company_cost = fields.Monetary(string="Costo Total Empresa", compute="_compute_totals", store=True)

    # Clasificación Contable DGII
    l10n_do_expense_type = fields.Selection(
        selection=lambda self: self.env["res.partner"]._get_l10n_do_expense_type(),
        string="Tipo de Gasto DGII",
        default="01", # 01 - Gastos de Personal
        required=True,
        help="Clasificación fiscal DGII oficial para reportes y deducciones (01 - Gastos de Personal)."
    )

    move_id = fields.Many2one("account.move", string="Asiento Contable", readonly=True, copy=False)

    @api.depends("wage_base", "overtime_amount", "commissions_amount", "other_deductions", "employee_id")
    def _compute_totals(self):
        for rec in self:
            gross = Decimal(str(rec.wage_base + rec.overtime_amount + rec.commissions_amount))
            is_exempt = rec.employee_id.l10n_do_is_exempt_isr if rec.employee_id else False
            other_ded = Decimal(str(rec.other_deductions or 0.0))

            res = calculate_dominican_payroll(
                gross_salary=gross,
                other_deductions=other_ded,
                is_exempt=is_exempt,
            )

            rec.gross_wage = float(res["gross_salary"])
            rec.sfs_employee = float(res["sfs_employee"])
            rec.afp_employee = float(res["afp_employee"])
            rec.total_tss_employee = float(res["total_tss_employee"])
            rec.taxable_base_isr = float(res["taxable_base_isr"])
            rec.isr_retention = float(res["isr_retention"])
            rec.total_deductions = float(res["total_deductions"])
            rec.net_wage = float(res["net_salary"])

            rec.sfs_employer = float(res["sfs_employer"])
            rec.afp_employer = float(res["afp_employer"])
            rec.srl_employer = float(res["srl_employer"])
            rec.infotep_employer = float(res["infotep"])
            rec.total_employer_contributions = float(res["total_employer_contributions"])
            rec.total_company_cost = float(res["total_company_cost"])

    def action_calculate(self):
        self._compute_totals()
        for rec in self:
            if rec.name == "/":
                rec.name = f"NOM/{rec.employee_id.name or 'EMP'}/{fields.Date.today().strftime('%Y%m')}"
            rec.state = "calculated"

    def action_draft(self):
        self.write({"state": "draft"})