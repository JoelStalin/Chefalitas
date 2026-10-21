# -*- coding: utf-8 -*-
import re
from werkzeug import urls

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError
from odoo.tools.sql import column_exists, create_column, drop_index, index_exists
from lxml import etree
import base64


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    l10n_do_itbis_amount = fields.Monetary(
        string="Monto de ITBIS",
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
        readonly=True,
    )

    l10n_do_discount_amount = fields.Monetary(
        string="Monto de Descuento",
        compute="_compute_l10n_do_discount_amount",
        store=True,
    )

    @api.depends("quantity", "discount", "price_unit", "tax_ids", "currency_id")
    def _compute_totals(self):
        """
        Calcula el monto de ITBIS por línea si aplica.
        Se ejecuta junto con la lógica estándar de Odoo.
        """
        super(AccountMoveLine, self)._compute_totals()  # Llama explícitamente al super de AccountMoveLine
        for line in self:
            # Solo aplica para líneas de producto
            if line.display_type != "product":
                line.l10n_do_itbis_amount = 0.0
                continue

            # Verificar si es una factura ECF
            if line.move_id.is_ecf_invoice:
                # Buscar grupo de impuesto ITBIS por nombre (más robusto)
                itbis_group = self.env["account.tax.group"].search([
                    ("name", "ilike", "ITBIS"),
                    ("company_id", "=", line.company_id.id),
                ], limit=1)

                # Filtrar impuestos ITBIS
                itbis_taxes = line.tax_ids.filtered(
                    lambda t: t.tax_group_id == itbis_group
                )

                # Aplicar descuento al precio unitario
                price_unit = line.price_unit * (1 - (line.discount / 100.0 or 0.0))

                # Calcular impuestos
                tax_data = itbis_taxes.compute_all(
                    price_unit=price_unit,
                    quantity=line.quantity,
                    currency=line.currency_id,
                    product=line.product_id,
                    partner=line.partner_id,
                )

                # Asignar el total del ITBIS
                line.l10n_do_itbis_amount = sum(
                    tax["amount"] for tax in tax_data.get("taxes", [])
                )
            else:
                line.l10n_do_itbis_amount = 0.0  # Si no es ECF, ITBIS es 0

    @api.depends('discount', 'price_unit', 'quantity')
    def _compute_l10n_do_discount_amount(self):
        for line in self:
            line.l10n_do_discount_amount = (line.discount / 100.0) * line.price_unit * line.quantity
    
    def _get_l10n_do_line_amounts(self):
        """
        Retorna un diccionario con los montos agrupados por tipo de impuesto (ITBIS, ISR).
        Incluye cálculos para diferentes tasas y retenciones.
        """
        # Works on all the journal items of ONE move at once.
        move = self.move_id[:1] if len(self.move_id) <= 1 else self.mapped("move_id").ensure_one()
        currency = move.currency_id
        company = move.company_id
        # Taxes are classified per tax (DGII 606: ITBIS vs ISR, facturado vs retenido).
        # ITBIS rates live in "ITBIS x%" groups and ISR in "ISR" groups; withholdings such as
        # "-100% ITBIS (R293-11)" live in the generic withholdings group, so the tax name
        # decides between ITBIS and ISR there.
        TaxGroup = self.env["account.tax.group"]
        groups_itbis = TaxGroup.search([("name", "ilike", "ITBIS"), ("company_id", "=", company.id)])
        groups_isr = TaxGroup.search([("name", "ilike", "ISR"), ("company_id", "=", company.id)])

        def _is_itbis(tax):
            return tax.tax_group_id in groups_itbis or (
                tax.tax_group_id not in groups_isr and "ITBIS" in (tax.name or "").upper())

        def _is_isr(tax):
            return tax.tax_group_id in groups_isr or (
                tax.tax_group_id not in groups_itbis and "ISR" in (tax.name or "").upper())

        # Separar líneas de impuestos por tipo
        itbis_tax_lines = self.filtered(lambda x: x.tax_line_id and _is_itbis(x.tax_line_id))
        isr_tax_lines = self.filtered(lambda x: x.tax_line_id and _is_isr(x.tax_line_id))

        # Separar líneas de producto facturables
        invoice_lines = self.filtered(lambda x: x.display_type == "product")
        taxed_lines = invoice_lines.filtered(lambda x: x.tax_ids.filtered("amount"))
        exempt_lines = invoice_lines - taxed_lines

        # Separar líneas con ITBIS e ISR
        itbis_taxed_lines = taxed_lines.filtered(
            lambda l: any(_is_itbis(t) for t in l.tax_ids.flatten_taxes_hierarchy())
        )
        isr_taxed_lines = taxed_lines.filtered(
            lambda l: any(_is_isr(t) for t in l.tax_ids.flatten_taxes_hierarchy())
        )

        # Mapas de tasas
        itbis_tax_amount_map = {
            "18": 18,
            "16": 16,
        }

        # Cálculos
        result = {
            "base_amount": sum(taxed_lines.mapped("price_subtotal")),
            "exempt_amount": sum(exempt_lines.mapped("price_subtotal")),
            "itbis_18_tax_amount": sum(
                currency.round(line.amount_currency)
                for line in itbis_tax_lines.filtered(
                    lambda l: l.tax_line_id.amount == itbis_tax_amount_map["18"]
                )
            ),
            "itbis_18_base_amount": sum(
                itbis_taxed_lines.filtered(
                    lambda l: any(
                        t.amount == itbis_tax_amount_map["18"] for t in l.tax_ids
                    )
                ).mapped("amount_currency")
            ),
            "itbis_16_tax_amount": sum(
                currency.round(line.amount_currency)
                for line in itbis_tax_lines.filtered(
                    lambda l: l.tax_line_id.amount == itbis_tax_amount_map["16"]
                )
            ),
            "itbis_16_base_amount": sum(
                itbis_taxed_lines.filtered(
                    lambda l: any(
                        t.amount == itbis_tax_amount_map["16"] for t in l.tax_ids
                    )
                ).mapped("amount_currency")
            ),
            "itbis_0_tax_amount": 0.0,  # no soportado
            "itbis_0_base_amount": 0.0,
            "itbis_withholding_amount": sum(
                currency.round(line.amount_currency)
                for line in itbis_tax_lines.filtered(
                    lambda l: l.tax_line_id.amount < 0
                )
            ),
            "itbis_withholding_base_amount": sum(
                itbis_taxed_lines.filtered(
                    lambda l: any(t.amount < 0 and _is_itbis(t) for t in l.tax_ids.flatten_taxes_hierarchy())
                ).mapped("amount_currency")
            ),
            "isr_withholding_amount": sum(
                currency.round(line.amount_currency)
                for line in isr_tax_lines.filtered(
                    lambda l: l.tax_line_id.amount < 0
                )
            ),
            "isr_withholding_base_amount": sum(
                isr_taxed_lines.filtered(
                    lambda l: any(t.amount < 0 and _is_isr(t) for t in l.tax_ids.flatten_taxes_hierarchy())
                ).mapped("amount_currency")
            ),
        }

        # Convertir todos los valores a positivos
        result = {k: abs(v) for k, v in result.items()}

        # Total general de la factura
        result["l10n_do_invoice_total"] = (
            move.amount_untaxed
            + result["itbis_18_tax_amount"]
            + result["itbis_16_tax_amount"]
        )

        # Conversión a moneda base si aplica
        if currency != company.currency_id:
            # Odoo 20: _get_rates returns {id: (rate, date)}; the conversion factor
            # (move currency -> company currency) is the stable API.
            factor = currency._get_conversion_rate(
                currency, company.currency_id, company, move.date or move.invoice_date
            )
            for k, v in list(result.items()):
                result[k + "_currency"] = v * factor

        return result