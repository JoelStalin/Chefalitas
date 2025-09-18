# -*- coding: utf-8 -*-
import re
from werkzeug import urls

from odoo import models, fields, api, _
from odoo.osv import expression
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
        # Buscar grupos de impuestos ITBIS e ISR
        group_itbis = self.env["account.tax.group"].search([
            ("name", "ilike", "ITBIS"),
            ("company_id", "=", self.company_id.id),
        ], limit=1)

        group_isr = self.env["account.tax.group"].search([
            ("name", "ilike", "ISR"),
            ("company_id", "=", self.company_id.id),
        ], limit=1)

        # Separar líneas de impuestos por grupo
        tax_lines = self.filtered(lambda x: x.tax_group_id in (group_itbis, group_isr))
        itbis_tax_lines = tax_lines.filtered(lambda x: x.tax_group_id == group_itbis)
        isr_tax_lines = tax_lines.filtered(lambda x: x.tax_group_id == group_isr)

        # Separar líneas de producto facturables
        invoice_lines = self.filtered(lambda x: x.display_type == "product")
        taxed_lines = invoice_lines.filtered(lambda x: x.tax_ids.filtered("amount"))
        exempt_lines = invoice_lines - taxed_lines

        # Separar líneas con ITBIS e ISR
        itbis_taxed_lines = taxed_lines.filtered(
            lambda l: group_itbis in l.tax_ids.mapped("tax_group_id")
        )
        isr_taxed_lines = taxed_lines.filtered(
            lambda l: group_isr in l.tax_ids.mapped("tax_group_id")
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
                self.currency_id.round(line.amount_currency)
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
                self.currency_id.round(line.amount_currency)
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
                self.currency_id.round(line.amount_currency)
                for line in itbis_tax_lines.filtered(
                    lambda l: l.tax_line_id.amount < 0
                )
            ),
            "itbis_withholding_base_amount": sum(
                itbis_taxed_lines.filtered(
                    lambda l: any(t.amount < 0 for t in l.tax_ids)
                ).mapped("amount_currency")
            ),
            "isr_withholding_amount": sum(
                self.currency_id.round(line.amount_currency)
                for line in isr_tax_lines.filtered(
                    lambda l: l.tax_line_id.amount < 0
                )
            ),
            "isr_withholding_base_amount": sum(
                isr_taxed_lines.filtered(
                    lambda l: any(t.amount < 0 for t in l.tax_ids)
                ).mapped("amount_currency")
            ),
        }

        # Convertir todos los valores a positivos
        result = {k: abs(v) for k, v in result.items()}

        # Total general de la factura
        result["l10n_do_invoice_total"] = (
            self.move_id.amount_untaxed
            + result["itbis_18_tax_amount"]
            + result["itbis_16_tax_amount"]
        )

        # Conversión a moneda base si aplica
        if self.currency_id != self.company_id.currency_id:
            rate = (self.currency_id + self.company_id.currency_id)._get_rates(
                self.company_id, self.move_id.date
            ).get(self.currency_id.id) or 1.0
            for k, v in list(result.items()):
                result[k + "_currency"] = v / rate

        return result