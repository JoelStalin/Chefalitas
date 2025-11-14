# -*- coding: utf-8 -*-
import json

from odoo import _, _lt, api, fields, models
from odoo.exceptions import ValidationError


class InvoiceServiceTypeDetail(models.Model):
    """
    Almacena los detalles de servicios para reportes DGII.
    Se usa como catálogo para desglosar el Tipo de Servicio (606 / 609).
    """
    _name = "invoice.service.type.detail"
    _description = _lt("Detalle del Tipo de Servicio DGII")

    name = fields.Char(string="Nombre", required=True)
    code = fields.Char(string="Código", size=2, required=True, index=True)
    parent_code = fields.Char(string="Código Padre")

    _sql_constraints = [
        (
            "code_unique",
            "unique(code)",
            _lt("El código debe ser único."),
        ),
    ]


class AccountMove(models.Model):
    """
    Extensión de facturas para reportes DGII (606 / 607 / 608 / 609).

    Estos campos se calculan a partir de:
      - Líneas de factura (invoice_line_ids)
      - Líneas contables (line_ids) con impuestos y cuentas fiscales
      - Estado de pago y reconciliaciones
    """
    _inherit = "account.move"

    # --- Campos DGII 606 (Compras) ---
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

    # --- Catálogo DGII de tipo de servicio / gasto ---
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
        "invoice.service.type.detail",
        string="Detalle del Tipo de Servicio",
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

    # Base sobre la que se aplica la retención de ISR
    amount_with_isr_withholding = fields.Monetary(
        string="Monto con Retención ISR",
        currency_field="company_currency_id",
    )

    # -------------------------------------------------------------------------
    #   CONSTRAINTS
    # -------------------------------------------------------------------------

    @api.constrains("line_ids")
    def _check_isr_tax(self):
        """
        No permite más de una retención ITBIS/ISR por factura.

        Se busca en las líneas de impuestos (tax_line_id) cualquier impuesto
        marcado como 'isr' o 'ritbis' (ver campo purchase_tax_type en account.tax).
        Si se repite el mismo tipo, se lanza error.
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
                        "Una factura no puede tener múltiples retenciones "
                        "fiscales (ISR/ITBIS)."
                    )
                )

    # -------------------------------------------------------------------------
    #   COMPUTES PRINCIPALES
    # -------------------------------------------------------------------------

    @api.depends(
        "move_type",
        "invoice_line_ids.price_subtotal",
        "invoice_line_ids.product_id.type",
    )
    def _compute_amount_fields(self):
        """
        Calcula:
          - service_total_amount: subtotal de líneas con product_id.type = 'service'
          - good_total_amount: subtotal del resto de productos

        Solo aplica para facturas de compra (in_invoice / in_refund),
        porque el 606 es de Compras.
        """
        purchase_types = ("in_invoice", "in_refund")
        for move in self:
            service_total = 0.0
            goods_total = 0.0

            if move.move_type in purchase_types:
                for line in move.invoice_line_ids:
                    amount = line.price_subtotal
                    if line.product_id and line.product_id.type == "service":
                        service_total += amount
                    else:
                        goods_total += amount

            move.service_total_amount = service_total
            move.good_total_amount = goods_total

    @api.depends("line_ids.tax_line_id", "line_ids.balance")
    def _compute_invoiced_itbis(self):
        """
        ITBIS facturado:
        Suma de las líneas de impuesto cuyo impuesto tiene
        purchase_tax_type = 'itbis'.
        Aplica tanto para compras (606) como para ventas (607).
        """
        for move in self:
            itbis_amount = 0.0
            for line in move.line_ids:
                tax = line.tax_line_id
                if tax and tax.purchase_tax_type == "itbis":
                    itbis_amount += line.balance
            move.invoiced_itbis = itbis_amount

    @api.depends(
        "move_type",
        "line_ids.tax_line_id",
        "line_ids.tax_line_id.purchase_tax_type",
        "line_ids.balance",
    )
    def _compute_withheld_taxes(self):
        """
        Calcula:
          - withholded_itbis / income_withholding para Compras (606)
          - third_withheld_itbis / third_income_withholding para Ventas (607)

        Según el campo purchase_tax_type del impuesto:
          - 'ritbis' => ITBIS retenido
          - 'isr'    => ISR retenido
        """
        purchase_types = ("in_invoice", "in_refund")
        sale_types = ("out_invoice", "out_refund")

        for move in self:
            wh_itbis = wh_isr = 0.0
            third_wh_itbis = third_wh_isr = 0.0
            isr_base = 0.0

            for line in move.line_ids:
                tax = line.tax_line_id
                if not tax:
                    continue

                tax_type = tax.purchase_tax_type

                # --- Compras: retención practicada a proveedores (606) ---
                if move.move_type in purchase_types:
                    if tax_type == "ritbis":
                        wh_itbis += line.balance
                    elif tax_type == "isr":
                        wh_isr += line.balance
                        # Base de ISR: usamos el total de la parte imponible de la factura
                        # si la línea tiene impuestos con 'isr', sumamos el subtotal
                        if line.tax_ids:
                            # En muchas implementaciones, las líneas con ISR tienen la
                            # retención ligada a la base de esa cuenta.
                            isr_base += abs(line.balance)

                # --- Ventas: retención efectuada por terceros (607) ---
                elif move.move_type in sale_types:
                    if tax_type == "ritbis":
                        third_wh_itbis += line.balance
                    elif tax_type == "isr":
                        third_wh_isr += line.balance
                        if line.tax_ids:
                            isr_base += abs(line.balance)

            move.withholded_itbis = wh_itbis
            move.income_withholding = wh_isr
            move.third_withheld_itbis = third_wh_itbis
            move.third_income_withholding = third_wh_isr
            move.amount_with_isr_withholding = isr_base

    @api.depends(
        "payment_state",
        "line_ids.account_id.account_type",
        "line_ids.matched_debit_ids",
        "line_ids.matched_credit_ids",
        "line_ids.tax_line_id",
        "line_ids.tax_line_id.purchase_tax_type",
        "line_ids.account_id.account_fiscal_type",
        "line_ids.balance",
    )
    def _compute_taxes_fields(self):
        """
        Calcula:
          - payment_date            (última fecha de pago real)
          - proportionality_tax     (ITBIS en cuentas A29/A30)
          - cost_itbis              (ITBIS en cuenta A51)
          - selective_tax           (Impuesto Selectivo)
          - other_taxes             (otros impuestos, excluyendo ITBIS y retenciones)
          - legal_tip               (propina legal)

        Se apoya en:
          - account_fiscal_type (A29, A30, A51, etc.)
          - purchase_tax_type    del impuesto
          - tax_group_id.name    para distinguir selectivo / propina
        """
        for move in self:
            # --- Fecha de pago ---
            pay_date = False
            if move.payment_state == "paid":
                payment_dates = set()
                # Líneas de cliente/proveedor
                rec_pay_lines = move.line_ids.filtered(
                    lambda l: l.account_id.account_type in ("asset_receivable", "liability_payable")
                )
                for line in rec_pay_lines:
                    partials = line.matched_debit_ids | line.matched_credit_ids
                    for partial in partials:
                        # max_date existe en versiones recientes; si no, usamos create_date
                        if getattr(partial, "max_date", False):
                            payment_dates.add(partial.max_date)
                        elif partial.create_date:
                            payment_dates.add(partial.create_date.date())
                if payment_dates:
                    pay_date = max(payment_dates)

            proportionality = 0.0
            cost_itbis = 0.0
            selective = 0.0
            others = 0.0
            legal_tip = 0.0

            for line in move.line_ids:
                tax = line.tax_line_id
                acc = line.account_id

                # --- ITBIS sujeto a proporcionalidad / llevado al costo ---
                if acc and acc.account_fiscal_type:
                    if acc.account_fiscal_type in ("A29", "A30"):
                        proportionality += line.balance
                    elif acc.account_fiscal_type == "A51":
                        cost_itbis += line.balance

                # --- Otros impuestos: Selectivo / Propina / Otros ---
                if tax:
                    group_name = (tax.tax_group_id.name or "").upper()
                    tax_type = tax.purchase_tax_type

                    # Selectivo al consumo (usamos el nombre del grupo)
                    if "SELECTIVO" in group_name:
                        selective += line.balance
                    # Propina legal
                    elif "PROPINA" in group_name:
                        legal_tip += line.balance
                    else:
                        # Otros impuestos distintos de ITBIS / retenciones / rext
                        if tax_type not in ("itbis", "ritbis", "isr", "rext"):
                            others += line.balance

            move.payment_date = pay_date
            move.proportionality_tax = proportionality
            move.cost_itbis = cost_itbis
            move.selective_tax = selective
            move.other_taxes = others
            move.legal_tip = legal_tip

    @api.depends("invoiced_itbis", "proportionality_tax", "cost_itbis", "move_type")
    def _compute_advance_itbis(self):
        """
        ITBIS por Adelantar:
          total ITBIS facturado
        - ITBIS llevado al costo
        - ITBIS sujeto a proporcionalidad

        Solo aplica para Compras (606).
        """
        purchase_types = ("in_invoice", "in_refund")
        for move in self:
            if move.move_type in purchase_types:
                move.advance_itbis = (
                    (move.invoiced_itbis or 0.0)
                    - (move.proportionality_tax or 0.0)
                    - (move.cost_itbis or 0.0)
                )
            else:
                move.advance_itbis = 0.0

    @api.depends("line_ids.tax_line_id", "line_ids.tax_line_id.purchase_tax_type")
    def _compute_isr_withholding_type(self):
        """
        Determina el código de tipo de retención ISR (01..08) para el 606,
        tomando el primer impuesto con purchase_tax_type = 'isr' que tenga
        isr_retention_type configurado.
        """
        for move in self:
            code = False
            for line in move.line_ids:
                tax = line.tax_line_id
                if (
                    tax
                    and tax.purchase_tax_type == "isr"
                    and tax.isr_retention_type
                ):
                    code = tax.isr_retention_type
                    break
            move.isr_withholding_type = code or False

    @api.depends("payment_state", "move_type")
    def _compute_in_invoice_payment_form(self):
        """
        Forma de Pago (606, columna 23).

        Regla simplificada (puedes afinarla más adelante):
          - Si es factura de compra:
              * not_paid / partial => "04" (Crédito)
              * paid               => "02" (Cheque/Transferencia/Depósito)
          - Para otros tipos, se deja vacío.
        """
        purchase_types = ("in_invoice", "in_refund")
        for move in self:
            code = False
            if move.move_type in purchase_types:
                if move.payment_state in ("not_paid", "partial"):
                    code = "04"  # Crédito
                elif move.payment_state == "paid":
                    code = "02"  # Cheque / Transferencia / Depósito
            move.payment_form = code

    @api.depends("partner_id.country_id", "company_id.country_id")
    def _compute_is_exterior(self):
        """
        Marca si la factura es del exterior (diferente país al de la compañía).
        Se usa como criterio para 609.
        """
        for move in self:
            company_country = move.company_id.country_id
            partner_country = move.partner_id.country_id
            move.is_exterior = bool(
                company_country
                and partner_country
                and company_country != partner_country
            )
