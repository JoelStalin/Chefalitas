# -*- coding: utf-8 -*-
import json

from odoo import _, _lt, api, fields, models
from odoo.exceptions import ValidationError


class InvoiceServiceTypeDetail(models.Model):
    """Almacena los detalles de servicios para reportes DGII."""

    _name = "invoice.service.type.detail"
    _description = _lt("Detalle del Tipo de Servicio DGII")

    name = fields.Char(string="Nombre", required=True)
    code = fields.Char(string="Código", size=2, required=True, index=True)
    parent_code = fields.Char(string="Código Padre")

    _sql_constraints = [
        ("code_unique", "unique(code)", _lt("El código debe ser único.")),
    ]


class AccountMove(models.Model):
    """Extensión de facturas para reportes DGII (606 / 607 / 608 / 609)."""

    _inherit = "account.move"

    # --- Campos DGII 606 ---
    service_total_amount = fields.Monetary(
        string="Monto Total de Servicios",
        compute="_compute_amount_fields",
        store=True,
        currency_field="company_currency_id",
    )
    good_total_amount = fields.Monetary(
        string="Monto Total de Bienes",
        compute="_compute_amount_fields",
        store=True,
        currency_field="company_currency_id",
    )

    invoiced_itbis = fields.Monetary(
        string="ITBIS Facturado",
        compute="_compute_invoiced_itbis",
        store=True,
        currency_field="company_currency_id",
    )

    withholded_itbis = fields.Monetary(
        string="ITBIS Retenido",
        compute="_compute_withheld_taxes",
        store=True,
        currency_field="company_currency_id",
    )
    income_withholding = fields.Monetary(
        string="ISR Retenido",
        compute="_compute_withheld_taxes",
        store=True,
        currency_field="company_currency_id",
    )

    third_withheld_itbis = fields.Monetary(
        string="ITBIS Retenido (Terceros)",
        compute="_compute_withheld_taxes",
        store=True,
        currency_field="company_currency_id",
    )
    third_income_withholding = fields.Monetary(
        string="ISR Retenido (Terceros)",
        compute="_compute_withheld_taxes",
        store=True,
        currency_field="company_currency_id",
    )

    payment_date = fields.Date(
        string="Fecha de Pago",
        compute="_compute_taxes_fields",
        store=True,
    )
    proportionality_tax = fields.Monetary(
        string="ITBIS Sujeto a Proporcionalidad",
        compute="_compute_taxes_fields",
        store=True,
        currency_field="company_currency_id",
    )
    cost_itbis = fields.Monetary(
        string="ITBIS Llevado al Costo",
        compute="_compute_taxes_fields",
        store=True,
        currency_field="company_currency_id",
    )
    selective_tax = fields.Monetary(
        string="Impuesto Selectivo al Consumo",
        compute="_compute_taxes_fields",
        store=True,
        currency_field="company_currency_id",
    )
    other_taxes = fields.Monetary(
        string="Otros Impuestos/Tasas",
        compute="_compute_taxes_fields",
        store=True,
        currency_field="company_currency_id",
    )
    legal_tip = fields.Monetary(
        string="Propina Legal",
        compute="_compute_taxes_fields",
        store=True,
        currency_field="company_currency_id",
    )

    advance_itbis = fields.Monetary(
        string="ITBIS por Adelantar",
        compute="_compute_advance_itbis",
        store=True,
        currency_field="company_currency_id",
    )

    isr_withholding_type = fields.Char(
        string="Tipo de Retención ISR",
        compute="_compute_isr_withholding_type",
        store=True,
        size=2,
    )

    payment_form = fields.Selection(
        [
            ("01", "Efectivo"),
            ("02", "Cheque / Transferencia / Depósito"),
            ("03", "Tarjeta Crédito / Débito"),
            ("04", "Crédito"),
            ("05", "Permuta"),
            ("06", "Nota de Crédito"),
            ("07", "Mixto"),
        ],
        string="Forma de Pago",
        compute="_compute_in_invoice_payment_form",
        store=True,
    )

    is_exterior = fields.Boolean(
        string="Factura del Exterior",
        compute="_compute_is_exterior",
        store=True,
    )
    service_type = fields.Selection(
        [
            ("01", "Gastos de Personal"),
            ("02", "Gastos por Trabajos, Suministros y Servicios"),
            ("03", "Arrendamientos"),
            ("04", "Gastos de Activos Fijos"),
            ("05", "Gastos de Representación"),
            ("06", "Gastos Financieros"),
            ("07", "Gastos de Seguros"),
            ("08", "Gastos por Regalías y otros Intangibles"),
        ],
        string="Tipo de Servicio",
    )
    service_type_detail = fields.Many2one(
        "invoice.service.type.detail", string="Detalle del Tipo de Servicio"
    )

    fiscal_status = fields.Selection(
        [
            ("normal", "Parcial"),
            ("done", "Reportado"),
            ("blocked", "No Enviado"),
        ],
        string="Estado Fiscal",
        copy=False,
        help=(
            "* Gris: La factura no está totalmente reportada y puede aparecer "
            "en otro reporte si se aplica una retención.\n"
            "* Verde: Factura totalmente reportada.\n"
            "* Rojo: Factura incluida en un reporte DGII no enviado.\n"
            "* En blanco: Factura aún no incluida en un reporte."
        ),
    )

    amount_with_isr_withholding = fields.Monetary(string="Monto con Retención ISR")

    @api.constrains("line_ids")
    def _check_isr_tax(self):
        """Restringe más de una retención ISR o ITBIS por factura.

        Usamos directamente ``line_ids`` en lugar de un helper inexistente
        (p. ej. ``_get_tax_line_ids``) para evitar errores de atributo
        durante la validación.
        """
        for inv in self:
            tax_types = [
                line.tax_line_id.purchase_tax_type
                for line in inv.line_ids
                if line.tax_line_id
                and line.tax_line_id.purchase_tax_type in ("isr", "ritbis")
            ]
            if len(tax_types) != len(set(tax_types)):
                raise ValidationError(
                    _(
                        "Una factura no puede tener múltiples retenciones fiscales (ISR/ITBIS)."
                    )
                )
