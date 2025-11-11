# -*- coding: utf-8 -*-
import re
from werkzeug import urls

from odoo import _, api, fields, models
from odoo.osv import expression
from odoo.exceptions import ValidationError, UserError, AccessError
from odoo.tools.sql import column_exists, create_column, drop_index, index_exists
from lxml import etree
import base64


class AccountMove(models.Model):
    _inherit = "account.move"
    _rec_names_search = ["l10n_do_fiscal_number"]

    _l10n_do_sequence_field = "l10n_do_fiscal_number"
    _l10n_do_sequence_fixed_regex = r"^(?P<prefix1>.*?)(?P<seq>\d{0,8})$"

    def _get_l10n_do_cancellation_type(self):
        return [
            ("01", _("01 - Deterioro del Comprobante")),
            ("02", _("02 - Errores de Impresión")),
            ("03", _("03 - Impresión Defectuosa")),
            ("04", _("04 - Corrección de Datos del Producto")),
            ("05", _("05 - Cambio de Producto")),
            ("06", _("06 - Devolución de Producto")),
            ("07", _("07 - Omisión de Producto")),
            ("08", _("08 - Error en Secuencia NCF")),
            ("09", _("09 - Cese de Operaciones")),
            ("10", _("10 - Pérdida del Talonario")),
        ]

    def _get_l10n_do_ecf_modification_code(self):
        return [
            ("1", _("01 - Cancelación Total")),
            ("2", _("02 - Corrección de Texto")),
            ("3", _("03 - Corrección de Monto")),
            ("4", _("04 - Sustitución por Contingencia")),
            ("5", _("05 - Referencia Factura Consumo")),
        ]

    def _get_l10n_do_income_type(self):
        return [
            ("01", _("01 - Ingresos Operacionales")),
            ("02", _("02 - Ingresos Financieros")),
            ("03", _("03 - Ingresos Extraordinarios")),
            ("04", _("04 - Ingresos por Arrendamiento")),
            ("05", _("05 - Venta de Activos Depreciables")),
            ("06", _("06 - Otros Ingresos")),
        ]

    l10n_do_fiscal_number = fields.Char(
        string="Número Fiscal",
        index="trigram",
        tracking=True,
        copy=False,
        help="Número de comprobante fiscal (NCF/e-CF)."
    )

    l10n_latam_manual_document_number = fields.Boolean(
        string="Número manual",
        store=True
    )

    l10n_do_expense_type = fields.Selection(
        selection=lambda self: self.env["res.partner"]._get_l10n_do_expense_type(),
        string="Tipo de Gasto",
    )

    l10n_do_income_type = fields.Selection(
        selection=_get_l10n_do_income_type,
        string="Tipo de Ingreso",
        copy=False,
        default=lambda self: self._context.get("l10n_do_income_type", "01"),
    )

    l10n_do_cancellation_type = fields.Selection(
        selection=_get_l10n_do_cancellation_type,
        string="Motivo de Cancelación",
        copy=False,
    )

    l10n_do_origin_ncf = fields.Char(string="NCF Modificado")
    l10n_do_ncf_expiration_date = fields.Date(string="Válido hasta")

    is_ecf_invoice = fields.Boolean(
        string="Es e-CF",
        compute="_compute_is_ecf_invoice",
        store=True,
    )

    l10n_do_ecf_modification_code = fields.Selection(
        selection=_get_l10n_do_ecf_modification_code,
        string="Modificación e-CF",
        copy=False,
    )

    l10n_do_ecf_security_code = fields.Char(string="Código de Seguridad e-CF", copy=False)
    l10n_do_ecf_sign_date = fields.Datetime(string="Fecha de Firma e-CF", copy=False)
    l10n_do_electronic_stamp = fields.Char(
        string="Sello Electrónico",
        compute="_compute_l10n_do_electronic_stamp",
        store=True,
    )

    l10n_do_sequence_prefix = fields.Char(
        string="Prefijo NCF",
        compute="_compute_split_sequence",
        store=True,
    )
    l10n_do_sequence_number = fields.Integer(
        string="Número NCF",
        compute="_compute_split_sequence",
        store=True,
    )

    l10n_do_enable_first_sequence = fields.Boolean(
        string="Habilitar primera secuencia fiscal",
        compute="_compute_l10n_do_enable_first_sequence",
        store=True,
        help="Permite asignar manualmente el primer comprobante fiscal interno si no existen previos publicados.",
    )

    l10n_do_ecf_edi_file = fields.Binary("Archivo XML e-CF", copy=False, readonly=True)
    l10n_do_ecf_edi_file_name = fields.Char("Nombre Archivo XML", copy=False, readonly=True)

    l10n_do_show_expiration_date_msg = fields.Boolean(
        string="Mostrar advertencia de vencimiento",
        compute="_compute_l10n_do_show_expiration_date_msg",
        help="Muestra advertencia si se debe ingresar número fiscal manual por vencimiento.",
    )
    l10n_do_company_in_contingency = fields.Boolean(
        string="En Contingencia",
        compute="_compute_company_in_contingency",
        store=True,
        help="Se activa si la empresa no tiene configurado un emisor de e-CF"
    )
    l10n_do_payment_method = fields.Selection([
        ('01', '01 - Efectivo'),
        ('02', '02 - Cheques/Transferencias/Depósitos'),
        ('03', '03 - Tarjeta Crédito/Débito'),
        ('04', '04 - Venta a Crédito'),
        ('05', '05 - Bonos / Certificados de Regalo'),
        ('06', '06 - Permuta'),
        ('07', '07 - Otros'),
        ('08', '08 - Mixto'),
    ], string="Forma de Pago", required=True,  default='01' )
    
    l10n_do_dgii_uuid = fields.Char(
        string="UUID DGII",
        readonly=True,
        copy=False,
        help="Identificador único devuelto por la DGII al recibir el e-CF"
    )
    
    itbis_amount = fields.Monetary(
        string='ITBIS 18%',
        currency_field='currency_id',
        compute='_compute_taxes_split',
        store=False,
    )
    propina_amount = fields.Monetary(
        string='Propina 10%',
        currency_field='currency_id',
        compute='_compute_taxes_split',
        store=False,
    )

    @api.depends('line_ids.tax_line_id', 'line_ids.balance')
    def _compute_taxes_split(self):
        for inv in self:
            lines = inv.line_ids.filtered(lambda l: l.tax_line_id)
            # Buscamos por nombre de impuesto
            inv.itbis_amount = abs(sum(
                lines.filtered(lambda l: l.tax_line_id.name == '18% ITBIS')
                     .mapped('balance')
            ))
            inv.propina_amount = abs(sum(
                lines.filtered(lambda l: l.tax_line_id.name == '10% Propina')
                     .mapped('balance')
            ))
    
    # _sql_constraints = [
    #     ("account_move_unique_l10n_do_fiscal_number_sales",
    #      "UNIQUE(l10n_do_fiscal_number, company_id)",
    #      "Ya existe otro documento con ese NCF en esta empresa."),
    # ]
    
    def _compute_tax_totals(self):
        super()._compute_tax_totals()
        for move in self:
            if not move.tax_totals:
                move.tax_totals = {'subtotals': [], 'amount_total': 0}
                
    @api.constrains("l10n_do_fiscal_number", "company_id")
    def _check_unique_fiscal_number(self):
        for rec in self.filtered(lambda r: r.l10n_do_fiscal_number and r.state != 'cancel'):
            domain = [
                ("id", "!=", rec.id),
                ("company_id", "=", rec.company_id.id),
                ("l10n_do_fiscal_number", "=", rec.l10n_do_fiscal_number),
                ("state", "!=", "cancel"),
            ]
            if self.search_count(domain):
                raise ValidationError(_("Ya existe otro documento con ese NCF en esta empresa."))



    def _auto_init(self):
        if not index_exists(self.env.cr, "account_move_account_move_unique_l10n_do_fiscal_number_sales"):
            drop_index(self.env.cr, "account_move_unique_l10n_do_fiscal_number_purchase_manual", self._table)
            drop_index(self.env.cr, "account_move_unique_l10n_do_fiscal_number_purchase_internal", self._table)

            if not column_exists(self.env.cr, "account_move", "l10n_do_fiscal_number"):
                create_column(self.env.cr, "account_move", "l10n_do_fiscal_number", "varchar")

            if not column_exists(self.env.cr, "account_move", "l10n_latam_manual_document_number"):
                create_column(self.env.cr, "account_move", "l10n_latam_manual_document_number", "varchar")

            self.env.cr.execute("""
                CREATE UNIQUE INDEX account_move_account_move_unique_l10n_do_fiscal_number_sales
                ON account_move(l10n_do_fiscal_number, company_id)
                WHERE (l10n_latam_document_type_id IS NOT NULL AND move_type NOT IN ('in_invoice', 'in_refund'))
                AND l10n_do_fiscal_number <> '';

                CREATE UNIQUE INDEX account_move_unique_l10n_do_fiscal_number_purchase_manual
                ON account_move(l10n_do_fiscal_number, commercial_partner_id, company_id)
                WHERE (l10n_latam_document_type_id IS NOT NULL AND move_type IN ('in_invoice', 'in_refund')
                AND l10n_latam_manual_document_number = 't') AND l10n_do_fiscal_number <> '';

                CREATE UNIQUE INDEX account_move_unique_l10n_do_fiscal_number_purchase_internal
                ON account_move(l10n_do_fiscal_number, company_id)
                WHERE (l10n_latam_document_type_id IS NOT NULL AND move_type IN ('in_invoice', 'in_refund', 'in_receipt')
                AND l10n_latam_manual_document_number = 'f') AND l10n_do_fiscal_number <> '';
            """)
        return super()._auto_init()


    @api.model
    def _name_search(self, name, domain=None, operator='ilike', limit=None, order=None):
        if name:
            domain = expression.AND([[
                "|",
                ("name", operator, name),
                ("l10n_do_fiscal_number", operator, name),
            ], domain])
        return super()._name_search(name, domain, operator, limit, order)

    def _l10n_do_is_new_expiration_date(self):
        self.ensure_one()
        last_invoice = self.search(
            [
                ("company_id", "=", self.company_id.id),
                ("move_type", "=", self.move_type),
                (
                    "l10n_latam_document_type_id",
                    "=",
                    self.l10n_latam_document_type_id.id,
                ),
                ("posted_before", "=", True),
                ("id", "!=", self.id or self._origin.id),
                ("l10n_do_ncf_expiration_date", "!=", False),
            ],
            order="invoice_date desc, id desc",
            limit=1,
        )
        if not last_invoice:
            return False

        return (
            last_invoice.l10n_do_ncf_expiration_date < self.l10n_do_ncf_expiration_date
        )

    @api.depends("l10n_do_ncf_expiration_date", "journal_id")
    def _compute_l10n_do_show_expiration_date_msg(self):
        for inv in self:
            if inv.country_code == "DO" and inv.l10n_latam_use_documents and inv.l10n_latam_document_type_id and not inv.l10n_latam_manual_document_number and inv.l10n_do_ncf_expiration_date:
                last_invoice = self.search([
                    ("company_id", "=", inv.company_id.id),
                    ("move_type", "=", inv.move_type),
                    ("l10n_latam_document_type_id", "=", inv.l10n_latam_document_type_id.id),
                    ("posted_before", "=", True),
                    ("id", "!=", inv.id or inv._origin.id),
                    ("l10n_do_ncf_expiration_date", "!=", False),
                ], order="invoice_date desc, id desc", limit=1)
                inv.l10n_do_show_expiration_date_msg = bool(last_invoice and last_invoice.l10n_do_ncf_expiration_date < inv.l10n_do_ncf_expiration_date)
            else:
                inv.l10n_do_show_expiration_date_msg = False

    @api.depends(
        "journal_id.l10n_latam_use_documents",
        "l10n_latam_manual_document_number",
        "l10n_latam_document_type_id",
        "company_id"
    )
    def _compute_l10n_do_enable_first_sequence(self):
        for invoice in self:
            # Valor por defecto (asignación obligatoria)
            invoice.l10n_do_enable_first_sequence = False

        # Aplicar lógica DGII sólo si se cumplen las condiciones
        for invoice in self.filtered(
            lambda inv: inv.country_code == "DO"
            and inv.l10n_latam_use_documents
            and inv.l10n_latam_document_type_id
            and not inv.l10n_latam_manual_document_number
        ):
            count = self.search_count([
                ("company_id", "=", invoice.company_id.id),
                ("move_type", "=", invoice.move_type),
                ("l10n_latam_document_type_id", "=", invoice.l10n_latam_document_type_id.id),
                ("posted_before", "=", True),
                ("id", "!=", invoice.id or invoice._origin.id),
            ])
            invoice.l10n_do_enable_first_sequence = (
                count == 0 or invoice.l10n_do_show_expiration_date_msg
            )

    def _get_l10n_do_amounts(self):
        self.ensure_one()
        amounts = {
            "base_amount": 0.0,
            "exempt_amount": 0.0,
            "itbis_18_tax_amount": 0.0,
            "itbis_18_base_amount": 0.0,
            "itbis_16_tax_amount": 0.0,
            "itbis_16_base_amount": 0.0,
            "itbis_0_tax_amount": 0.0,
            "itbis_0_base_amount": 0.0,
            "itbis_withholding_amount": 0.0,
            "itbis_withholding_base_amount": 0.0,
            "isr_withholding_amount": 0.0,
            "isr_withholding_base_amount": 0.0,
            "l10n_do_invoice_total": 0.0,
        }
        for line in self.line_ids.filtered(lambda l: l.currency_id == self.currency_id):
            line_amounts = line._get_l10n_do_line_amounts()
            for key in amounts:
                amounts[key] += line_amounts.get(key, 0.0)
        return amounts
    
    @api.depends("company_id", "l10n_latam_document_type_id")
    def _compute_is_ecf_invoice(self):
        for invoice in self.filtered(lambda inv: inv.state == "draft"):
            invoice.is_ecf_invoice = (
                invoice.country_code == "DO"
                and invoice.l10n_latam_document_type_id
                and invoice.l10n_latam_document_type_id.l10n_do_ncf_type
                and invoice.l10n_latam_document_type_id.l10n_do_ncf_type.startswith("e-")
            )

    @api.depends("company_id", "company_id.l10n_do_ecf_issuer", "is_ecf_invoice")
    def _compute_company_in_contingency(self):
        for invoice in self.filtered(lambda inv: inv.state == "draft" and inv.country_code == "DO" and inv.is_ecf_invoice):
            contingency = not invoice.company_id.l10n_do_ecf_issuer
            invoice.l10n_do_company_in_contingency = contingency

            if contingency and not invoice.l10n_latam_manual_document_number:
                # Buscar tipo de documento de contingencia según el tipo original
                contingency_type = invoice.env["l10n_latam.document.type"].search([
                    ("code", "in", ["E44", "E45"]),  # E44 = consumo, E45 = crédito fiscal
                    ("country_id.code", "=", "DO"),
                ])
                # Determinar si es crédito o consumo original
                if invoice.l10n_latam_document_type_id.l10n_do_ncf_type in ("e-credit", "credit"):
                    new_doc_type = contingency_type.filtered(lambda d: d.code == "E45")
                else:
                    new_doc_type = contingency_type.filtered(lambda d: d.code == "E44")

                if new_doc_type:
                    invoice.l10n_latam_document_type_id = new_doc_type.id
                    invoice.l10n_latam_manual_document_number = True


    @api.depends("l10n_do_ecf_security_code", "l10n_do_ecf_sign_date", "invoice_date")
    def _compute_l10n_do_electronic_stamp(self):
        ecf_invoices = self.filtered(
            lambda i: i.is_ecf_invoice and not i.l10n_latam_manual_document_number and i.l10n_do_ecf_security_code and i.state == "posted"
        )
        for invoice in ecf_invoices:
            env_type = invoice.company_id.l10n_do_ecf_service_env or "TesteCF"
            prefix = invoice.l10n_latam_document_type_id.doc_code_prefix
            is_rfc = prefix == "E32" and invoice.amount_total_signed < 250000
            base_url = f"https://{'fc' if is_rfc else 'ecf'}.dgii.gov.do/{env_type}/ConsultaTimbre{'FC' if is_rfc else ''}?"
            query = {
                "RncEmisor": invoice.company_id.vat or "",
                "ENCF": invoice.l10n_do_fiscal_number or "",
            }
            if not is_rfc:
                if prefix[1:] not in ("43", "47"):
                    query["RncComprador"] = invoice.commercial_partner_id.vat or ""
                query["FechaEmision"] = (invoice.invoice_date or fields.Date.today()).strftime("%d-%m-%Y")
                query["FechaFirma"] = invoice.l10n_do_ecf_sign_date.strftime("%d-%m-%Y %H:%M:%S")
            total_field = "l10n_do_invoice_total"
            if invoice.currency_id != invoice.company_id.currency_id:
                total_field += "_currency"
            total = invoice._get_l10n_do_amounts().get(total_field, 0)
            query["MontoTotal"] = ("%f" % total).rstrip("0").rstrip(".")
            security_code = "".join(
                f"%{c.encode('utf-8').hex()}".upper() if c in " !#$&'()*+,/:;=?@[]\"-.<>\\^_`" else c
                for c in invoice.l10n_do_ecf_security_code or ""
            )
            query["CodigoSeguridad"] = security_code
            qr_string = base_url + "&".join(f"{k}={v}" for k, v in query.items())
            invoice.l10n_do_electronic_stamp = urls.url_quote_plus(qr_string, safe="%")
        (self - ecf_invoices).l10n_do_electronic_stamp = False

    
    @api.constrains(
        "l10n_do_fiscal_number", "partner_id", "company_id", "posted_before"
    )
    def _l10n_do_check_unique_vendor_number(self):
        for rec in self.filtered(
            lambda inv: inv.l10n_do_fiscal_number
            and inv.country_code == "DO"
            and inv.l10n_latam_use_documents
            and inv.is_purchase_document()
            and inv.commercial_partner_id
        ):
            domain = [
                ("move_type", "=", rec.move_type),
                ("l10n_do_fiscal_number", "=", rec.l10n_do_fiscal_number),
                ("company_id", "=", rec.company_id.id),
                ("id", "!=", rec.id),
                ("commercial_partner_id", "=", rec.commercial_partner_id.id),
                ("state", "!=", "cancel"),
            ]
            if rec.search_count(domain):
                raise ValidationError(
                    _(
                        "Vendor bill Fiscal Number must be unique per vendor and company."
                    )
                )

    @api.depends("l10n_do_fiscal_number")
    def _compute_l10n_latam_document_number(self):
        l10n_do_recs = self.filtered(
            lambda x: x.country_code == "DO" and x.l10n_latam_use_documents
        )
        for rec in l10n_do_recs:
            rec.l10n_latam_document_number = rec.l10n_do_fiscal_number

        super(AccountMove, self - l10n_do_recs)._compute_l10n_latam_document_number()

    def button_cancel(self):
        fiscal_invoice = self.filtered(lambda r: r.country_code == "DO" and r.move_type[-6:] in ("nvoice", "refund") and r.l10n_latam_use_documents)
        not_ecf = fiscal_invoice.filtered(lambda i: not i.is_ecf_invoice)
        if len(fiscal_invoice) > 1:
            raise ValidationError(_("No puedes cancelar múltiples comprobantes fiscales a la vez."))
        if not_ecf and not self.env.user.has_group("l10n_do_accounting.group_l10n_do_fiscal_invoice_cancel"):
            raise AccessError(_("No tienes permiso para cancelar comprobantes fiscales."))
        if fiscal_invoice and not fiscal_invoice.posted_before:
            raise ValidationError(_("No puedes cancelar un comprobante que no ha sido publicado previamente."))
        if not_ecf and not self.env.context.get("skip_cancel_wizard", False):
            action = self.env.ref("l10n_do_accounting.action_account_move_cancel").sudo().read()[0]
            action["context"] = {"default_move_id": fiscal_invoice.id}
            return action
        if fiscal_invoice:
            fiscal_invoice.button_draft()
        return super().button_cancel()
    
    def action_reverse(self):
        fiscal_invoice = self.filtered(
            lambda inv: inv.country_code == "DO"
            and self.move_type[-6:] in ("nvoice", "refund")
        )
        if fiscal_invoice and not self.env.user.has_group(
            "l10n_do_accounting.group_l10n_do_fiscal_credit_note"
        ):
            raise AccessError(_("No tienes permiso para emitir notas de crédito fiscales."))

        return super(AccountMove, self).action_reverse()

    @api.onchange("l10n_latam_document_type_id", "l10n_latam_document_number")
    def _inverse_l10n_latam_document_number(self):
        for rec in self.filtered("l10n_latam_document_type_id"):
            if not rec.l10n_latam_document_number:
                rec.l10n_do_fiscal_number = ""
            else:
                document_type_id = rec.l10n_latam_document_type_id
                if document_type_id.l10n_do_ncf_type:
                    document_number = document_type_id._format_document_number(
                        rec.l10n_latam_document_number
                    )
                else:
                    document_number = rec.l10n_latam_document_number

                if rec.l10n_latam_document_number != document_number:
                    rec.l10n_latam_document_number = document_number
                rec.l10n_do_fiscal_number = document_number
        super(
            AccountMove, self.filtered(lambda m: m.country_code != "DO")
        )._inverse_l10n_latam_document_number()

    def _get_l10n_latam_documents_domain(self):
        self.ensure_one()
        if not (
            self.journal_id.l10n_latam_use_documents
            and self.journal_id.company_id.country_id == self.env.ref("base.do")
        ):
            return super()._get_l10n_latam_documents_domain()

        internal_types = ["debit_note"]
        if self.move_type in ["out_refund", "in_refund"]:
            internal_types.append("credit_note")
        else:
            internal_types.append("invoice")

        domain = [
            ("internal_type", "in", internal_types),
            ("country_id", "=", self.company_id.country_id.id),
        ]
        ncf_types = self.journal_id._get_journal_ncf_types(
            counterpart_partner=self.partner_id.commercial_partner_id, invoice=self
        )
        domain += [
            "|",
            ("l10n_do_ncf_type", "=", False),
            ("l10n_do_ncf_type", "in", ncf_types),
        ]
        codes = self.journal_id._get_journal_codes()
        if codes:
            domain.append(("code", "in", codes))
        return domain

    @api.constrains("move_type", "l10n_latam_document_type_id")
    def _check_invoice_type_document_type(self):
        l10n_do_invoices = self.filtered(
            lambda inv: inv.country_code == "DO"
            and inv.l10n_latam_use_documents
            and inv.l10n_latam_document_type_id
            and inv.state == "posted"
        )
        for rec in l10n_do_invoices:
            has_vat = bool(rec.partner_id.vat and bool(rec.partner_id.vat.strip()))
            l10n_latam_document_type = rec.l10n_latam_document_type_id
            if not has_vat and (
                rec.amount_untaxed_signed >= 250000
                or (
                    l10n_latam_document_type.is_vat_required
                    and rec.commercial_partner_id.l10n_do_dgii_tax_payer_type
                    != "non_payer"
                )
            ):
                raise ValidationError(
                    _(
                        "A VAT is mandatory for this type of NCF. "
                        "Please set the current VAT of this client"
                    )
                )
        super(AccountMove, self - l10n_do_invoices)._check_invoice_type_document_type()

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if (
            self.company_id.country_id == self.env.ref("base.do")
            and self.l10n_latam_document_type_id
            and self.move_type == "in_invoice"
            and self.partner_id
        ):
            if not self.l10n_do_expense_type:
                    self.l10n_do_expense_type = self.partner_id.l10n_do_expense_type
        return super(AccountMove, self)._onchange_partner_id()

    def _reverse_move_vals(self, default_values, cancel=True):
        ctx = self.env.context
        amount = ctx.get("amount")
        percentage = ctx.get("percentage")
        refund_type = ctx.get("refund_type")
        reason = ctx.get("reason")
        ecf_mod_code = ctx.get("l10n_do_ecf_modification_code")

        res = super()._reverse_move_vals(default_values, cancel)
        if self.country_code != "DO":
            return res

        res["l10n_do_origin_ncf"] = self.l10n_do_fiscal_number or self.ref
        res["l10n_do_ecf_modification_code"] = ecf_mod_code

        if refund_type in ("percentage", "fixed_amount"):
            price_unit = amount if refund_type == "fixed_amount" else self.amount_untaxed * (percentage / 100)
            res["line_ids"] = False
            res["invoice_line_ids"] = [(0, 0, {"name": reason or _("Reembolso"), "price_unit": price_unit})]
        return res
    @api.depends("l10n_latam_document_type_id", "journal_id")
    def _compute_l10n_latam_manual_document_number(self):
        l10n_do_recs_with_journal_id = self.filtered(
            lambda x: x.journal_id
            and x.journal_id.l10n_latam_use_documents
            and x.l10n_latam_document_type_id
            and x.country_code == "DO"
        )
        for move in l10n_do_recs_with_journal_id:
            move.l10n_latam_manual_document_number = (
                move._is_l10n_do_manual_document_number()
            )

            move.l10n_do_ncf_expiration_date = (
                move.journal_id.l10n_do_document_type_ids.filtered(
                    lambda doc: doc.l10n_latam_document_type_id
                    == move.l10n_latam_document_type_id
                ).l10n_do_ncf_expiration_date
            )

        super(
            AccountMove, self - l10n_do_recs_with_journal_id
        )._compute_l10n_latam_manual_document_number()
        
    def _prepare_tax_totals(self):
        result = super()._prepare_tax_totals()
        if not isinstance(result, dict):
            return {}
        return result
    
    def _is_l10n_do_manual_document_number(self):
        self.ensure_one()

        if self.reversed_entry_id:
            return self.reversed_entry_id.l10n_latam_manual_document_number

        return self.move_type in (
            "in_invoice",
            "in_refund",
        ) and self.l10n_latam_document_type_id.l10n_do_ncf_type not in (
            "minor",
            "e-minor",
            "informal",
            "e-informal",
            "exterior",
            "e-exterior",
        )

    def _get_debit_line_tax(self, debit_date):
        if self.move_type == "out_invoice":
            return (
                self.company_id.account_sale_tax_id
                or self.env.ref("account.%s_tax_18_sale" % self.company_id.id)
                if (debit_date - self.invoice_date).days <= 30
                and self.partner_id.l10n_do_dgii_tax_payer_type != "special"
                else self.env.ref("account.%s_tax_0_sale" % self.company_id.id) or False
            )
        else:
            return self.company_id.account_purchase_tax_id or self.env.ref(
                "account.%s_tax_0_purch" % self.company_id.id
            )

    def _post(self, soft=True):
        """Asegura que las facturas dominicanas obtengan el siguiente NCF al publicar."""
        l10n_do_invoices = self.filtered(
            lambda inv: inv.country_code == "DO" and inv.l10n_latam_use_documents
        )
        
        for invoice in l10n_do_invoices:
            if invoice.move_type in ('out_invoice', 'out_refund') and not invoice.l10n_do_fiscal_number:
                # Forzar la generación del siguiente NCF antes de publicar
                invoice.with_context(is_l10n_do_seq=True)._set_next_sequence()
                invoice.name = invoice.l10n_do_fiscal_number

        res = super()._post(soft)

        # Validaciones adicionales para facturas dominicanas
        for invoice in l10n_do_invoices.filtered(lambda inv: inv.l10n_latam_document_type_id):
            if not invoice.amount_total:
                raise UserError(_("No se puede publicar un comprobante fiscal con monto cero."))
            if not invoice.partner_id.l10n_do_dgii_tax_payer_type:
                raise ValidationError(_("Los comprobantes fiscales requieren que el socio tenga tipo fiscal."))

        return res

    def _l10n_do_get_formatted_sequence(self):
        self.ensure_one()
        if not self._context.get("is_l10n_do_seq", False):
            year = self.date.year
            base = f"{self.journal_id.code}/{year}/0000"
            if self.journal_id.refund_sequence and self.move_type in ("out_refund", "in_refund"):
                base = f"R{base}"
            return base

        doc_type = self.l10n_latam_document_type_id
        return f"{doc_type.doc_code_prefix}{''.zfill(10 if str(doc_type.l10n_do_ncf_type).startswith('e-') else 8)}"

    def _get_starting_sequence(self):
        """Define la secuencia inicial para facturas dominicanas."""
        if self.country_code == "DO" and self.l10n_latam_use_documents:
            doc_type = self.l10n_latam_document_type_id
            return f"{doc_type.doc_code_prefix}{'0'.zfill(8)}"
        return super()._get_starting_sequence()
    def _sequence_matches_date(self):
        """Desactiva completamente la validación de fecha para facturas dominicanas."""
        if self.country_code == "DO" and self.l10n_latam_use_documents and self.l10n_do_fiscal_number:
            return True  # El NCF no incluye fecha, por lo que siempre es válido
        return super()._sequence_matches_date()
    
    def _get_name_invoice_report(self):
        self.ensure_one()
        if self.country_code == 'DO' and self.l10n_latam_use_documents:
            return 'l10n_do_accounting.report_invoice_document_inherited'
        return super()._get_name_invoice_report()
    
    def _get_last_sequence_domain(self, relaxed=False):
        where_string, param = super(AccountMove, self)._get_last_sequence_domain(
            relaxed
        )

        if self.l10n_latam_use_documents and self.country_code == "DO":
            where_string = where_string.replace(
                "AND sequence_prefix !~ %(anti_regex)s ", ""
            )
        if self._context.get("is_l10n_do_seq", False):
            where_string = where_string.replace("journal_id = %(journal_id)s AND", "")
            where_string += (
                " AND l10n_latam_document_type_id = %(l10n_latam_document_type_id)s AND"
                " company_id = %(company_id)s AND l10n_do_sequence_prefix != ''"
                " AND l10n_do_sequence_prefix IS NOT NULL"
            )
            if (
                not self.l10n_latam_manual_document_number
                and self.move_type != "in_refund"
            ):
                where_string += " AND move_type = %(move_type)s"
                param["move_type"] = self.move_type
            else:
                where_string += " AND l10n_latam_manual_document_number = 'f'"

            param["company_id"] = self.company_id.id or False
            param["l10n_latam_document_type_id"] = (
                self.l10n_latam_document_type_id.id or 0
            )
        return where_string, param

    # @api.constrains('invoice_line_ids')
    # def _check_tax_lines(self):
    #     for move in self:
    #         if move.move_type in ('out_invoice', 'out_refund') and not move.tax_totals:
    #             raise ValidationError(_("La factura debe tener impuestos configurados."))
            
    @api.depends("l10n_do_fiscal_number")
    def _compute_split_sequence(self):
        for rec in self:
            sequence = rec[rec._l10n_do_sequence_field] or ""
            regex = re.sub(r"\?P<\w+>", "?:", rec._l10n_do_sequence_fixed_regex.replace(r"?P<seq>", ""))
            match = re.match(regex, sequence)
            rec.l10n_do_sequence_prefix = sequence[:3]
            rec.l10n_do_sequence_number = int(match.group(1) or 0) if match else 0

    def _get_last_sequence(self, relaxed=False, with_prefix=None):
        """Ajusta la obtención de la última secuencia para facturas dominicanas."""
        if not (self.country_code == "DO" and self.l10n_latam_use_documents):
            return super()._get_last_sequence(relaxed=relaxed, with_prefix=with_prefix)

        self.ensure_one()
        where, params = self._get_last_sequence_domain(relaxed)
        if self.id or self._origin.id:
            where += " AND id != %(id)s "
            params["id"] = self.id or self._origin.id

        query = f"""
            SELECT {self._l10n_do_sequence_field}
            FROM {self._table}
            {where}
            ORDER BY l10n_do_sequence_number DESC
            LIMIT 1
        """
        self.flush_model([self._l10n_do_sequence_field, "l10n_do_sequence_number", "l10n_do_sequence_prefix"])
        self.env.cr.execute(query, params)
        return (self.env.cr.fetchone() or [None])[0]
    def _get_sequence_format_param(self, previous):
        """Formatea la secuencia para facturas dominicanas, incluyendo claves de fecha para compatibilidad."""
        if not (self.country_code == "DO" and self.l10n_latam_use_documents):
            return super()._get_sequence_format_param(previous)

        regex = self._l10n_do_sequence_fixed_regex
        match = re.match(regex, previous or "")
        doc_type = self.l10n_latam_document_type_id
        date = self.invoice_date or fields.Date.today()

        if match:
            format_values = match.groupdict()
        else:
            format_values = {
                "prefix1": doc_type.doc_code_prefix,
                "seq": "0",
                "year": str(date.year),  # Año para compatibilidad
                "month": str(date.month).zfill(2),  # Mes para compatibilidad
                "day": str(date.day).zfill(2),  # Día para compatibilidad
            }
        
        format_values["seq_length"] = 8
        format_values["seq"] = int(format_values.get("seq") or 0)
        format_values["year"] = str(date.year)
        format_values["month"] = str(date.month).zfill(2)
        format_values["day"] = str(date.day).zfill(2)

        # Formato para NCF dominicano (sin incluir fecha en la salida visible)
        fmt = "{prefix1}{seq:0{seq_length}d}"
        return fmt, format_values
   
    def _set_next_sequence(self):
        """Forza la generación del siguiente número de secuencia para facturas dominicanas."""
        self.ensure_one()
        if not (self.country_code == "DO" and self.l10n_latam_use_documents):
            return super()._set_next_sequence()

        # Obtener la última secuencia
        last_seq = self._get_last_sequence()
        new = not last_seq
        if new:
            last_seq = self._get_last_sequence(relaxed=True) or self._get_starting_sequence()

        # Generar el siguiente número
        fmt, fmt_values = self._get_sequence_format_param(last_seq)
        if new:
            fmt_values["seq"] = 0
        fmt_values["seq"] += 1

        # Asignar el número fiscal sin condiciones restrictivas
        self[self._l10n_do_sequence_field] = self.l10n_latam_document_type_id._format_document_number(
            fmt.format(**fmt_values)
        )
        self._compute_split_sequence()
    
    # TODO: handle l10n_latam_invoice_document _compute_name() inheritance shit
    @api.depends("l10n_do_fiscal_number", "move_type", "country_code", "l10n_latam_use_documents")
    def _compute_name(self):
        """Ajusta el campo `name` para usar `l10n_do_fiscal_number` en facturas dominicanas."""
        for move in self:
            if move.country_code == "DO" and move.l10n_latam_use_documents and move.move_type in ('out_invoice', 'out_refund'):
                if move.l10n_do_fiscal_number:
                    move.name = move.l10n_do_fiscal_number
                elif move.state == "draft" and not move.name:
                    move.name = "/"
            else:
                # Lógica predeterminada de Odoo para otros países
                super(AccountMove, move)._compute_name()
                
    def unlink(self):
        if self.filtered(
            lambda inv: inv.is_purchase_document()
            and inv.country_code == "DO"
            and inv.l10n_latam_use_documents
            and inv.posted_before
        ):
            raise UserError(_("No puedes eliminar un comprobante fiscal que ya fue publicado."))
        return super().unlink()
    # Extension of the _deduce_sequence_number_reset function to compute the `name` field according to the invoice
    # date and prevent the `l10n_latam_document_number` field from being reset
    @api.model
    def _deduce_sequence_number_reset(self, name):
        if (
            self.l10n_latam_use_documents
            and self.company_id.country_id.code == "DO"
            and self.posted_before
            and not self._context.get("is_l10n_do_seq", False)
        ):
            return "year"
        elif self._context.get("is_l10n_do_seq", False):
            return "never"
        return super()._deduce_sequence_number_reset(name)
    @api.constrains("l10n_latam_document_type_id", "partner_id")
    def _check_ncf_receiver_requirements(self):
        for inv in self:
            if inv.country_code != "DO":
                continue

            ncf_type = inv.l10n_latam_document_type_id.l10n_do_ncf_type
            vat = inv.partner_id.vat and inv.partner_id.vat.strip()
            if ncf_type in ["e-credit", "credit", "e-goverment"]:
                if not vat:
                    raise ValidationError(_("Este tipo de NCF requiere que el cliente tenga RNC o cédula."))

            if inv.amount_total >= 250000 and not vat:
                raise ValidationError(_("Para montos iguales o mayores a RD$250,000 es obligatorio el RNC/Cédula."))
    def _validate_ecf_xml_schema(self):
        self.ensure_one()
        if not self.l10n_do_ecf_edi_file:
            return

        xsd_path = get_module_resource('l10n_do_accounting', 'static', 'xsd', 'ECFv1_3.xsd')
        with open(xsd_path, 'rb') as f:
            schema_doc = etree.XML(f.read())
            schema = etree.XMLSchema(schema_doc)

        xml_data = base64.b64decode(self.l10n_do_ecf_edi_file)
        doc = etree.XML(xml_data)
        try:
            schema.assertValid(doc)
        except Exception as e:
            raise ValidationError(_("El archivo e-CF no es válido según el XSD: %s") % str(e))
