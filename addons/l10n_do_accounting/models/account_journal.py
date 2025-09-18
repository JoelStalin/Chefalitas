from odoo import fields, models, api, _
from odoo.exceptions import RedirectWarning, ValidationError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def _get_l10n_do_payment_form(self):
        """Devuelve las formas de pago permitidas por la DGII."""
        return [
            ("cash", _("Efectivo")),
            ("bank", _("Cheque / Transferencia")),
            ("card", _("Tarjeta de Crédito")),
            ("credit", _("Crédito")),
            ("swap", _("Permuta")),
            ("bond", _("Bonos o Certificados de Regalo")),
            ("others", _("Otro tipo de venta")),
        ]

    l10n_do_payment_form = fields.Selection(
        selection="_get_l10n_do_payment_form",
        string="Forma de Pago",
    )

    l10n_do_document_type_ids = fields.One2many(
        "l10n_do.account.journal.document_type",
        "journal_id",
        string="Tipos de Comprobante",
        copy=False,
    )

    def _get_all_ncf_types(self, types_list, invoice=False):
        """
        Devuelve lista de tipos NCF incluyendo ECF si la compañía es emisora.
        """
        ecf_types = ["e-%s" % d for d in types_list if d not in ("unique", "import")]

        if self.env.context.get("use_documents", False) or not invoice:
            return types_list + ecf_types

        if invoice.is_purchase_document() and any(
            t in types_list for t in ("minor", "informal", "exterior")
        ):
            return ecf_types if self.company_id.l10n_do_ecf_issuer else types_list

        return types_list + ecf_types

    @api.model
    def _get_l10n_do_ncf_types_data(self):
        """Define qué tipos NCF están permitidos según el tipo de contribuyente."""
        return {
            "issued": {
                "taxpayer": ["fiscal"],
                "non_payer": ["consumer", "unique"],
                "nonprofit": ["fiscal"],
                "special": ["special"],
                "governmental": ["governmental"],
                "foreigner": ["export", "consumer"],
            },
            "received": {
                "taxpayer": ["fiscal"],
                "non_payer": ["informal", "minor"],
                "nonprofit": ["special", "governmental"],
                "special": ["fiscal", "special", "governmental"],
                "governmental": ["fiscal", "special", "governmental"],
                "foreigner": ["import", "exterior"],
            },
        }

    def _get_journal_ncf_types(self, counterpart_partner=False, invoice=False):
        """
        Determina los tipos de comprobantes válidos según el tipo de diario,
        el socio y si la compañía es emisora de ECF.
        """
        self.ensure_one()
        ncf_data = self._get_l10n_do_ncf_types_data()

        if not self.company_id.vat:
            try:
                action = self.env.ref("base.action_res_company_form")
            except ValueError:
                action = False
            raise RedirectWarning(
                _("No puedes configurar comprobantes fiscales hasta definir el RNC de la empresa."),
                action.id if action else False,
                _("Ir a Compañías"),
            )

        tipo_emision = "issued" if self.type == "sale" else "received"
        tipos_ncf = list(set(
            tipo for contribuyente in ncf_data[tipo_emision].values()
            for tipo in contribuyente
        ))

        if not counterpart_partner:
            notas = ["debit_note", "credit_note"]
            externos = ["fiscal", "special", "governmental"]

            resultado = (
                tipos_ncf + notas
                if self.type == "sale"
                else [t for t in tipos_ncf if t not in externos]
            )
            return self._get_all_ncf_types(resultado)

        # Validación con partner
        if counterpart_partner.l10n_do_dgii_tax_payer_type:
            if counterpart_partner == self.company_id.partner_id:
                tipos_ncf = ["minor"]
            else:
                permitidos = ncf_data[tipo_emision][counterpart_partner.l10n_do_dgii_tax_payer_type]
                tipos_ncf = list(set(tipos_ncf) & set(permitidos))
        else:
            raise ValidationError(
                _("El socio (%s) debe tener definido su tipo de contribuyente para emitir comprobantes fiscales.")
                % counterpart_partner.name
            )

        # Validación para notas de crédito o débito
        if invoice and invoice.move_type in ["out_refund", "in_refund"]:
            tipos_ncf = ["credit_note"]

        if invoice and invoice.debit_origin_id or self.env.context.get("internal_type") == "debit_note":
            return ["debit_note", "e-debit_note"]

        return self._get_all_ncf_types(tipos_ncf, invoice)

    def _get_journal_codes(self):
        """Devuelve el prefijo de código de comprobante fiscal (B/E)."""
        self.ensure_one()
        if self.type == "purchase":
            return []
        elif self.type == "sale" and self.company_id.l10n_do_ecf_issuer:
            return ["E"]
        return ["B"]

    def _l10n_do_create_document_types(self):
        """Crea los tipos de documentos fiscales en el diario según la configuración."""
        self.ensure_one()
        if not self.l10n_latam_use_documents or self.company_id.country_id.code != "DO":
            return

        tipos_ncf = self._get_journal_ncf_types()

        if self.type == "purchase":
            tipos_ncf = [
                tipo for tipo in tipos_ncf if tipo not in ("fiscal", "credit_note")
            ]

        documentos = self.env["l10n_latam.document.type"].search([
            ("country_id.code", "=", "DO"),
            ("l10n_do_ncf_type", "in", tipos_ncf),
        ])

        ya_existentes = self.l10n_do_document_type_ids.mapped("l10n_latam_document_type_id.l10n_do_ncf_type")
        nuevos = documentos.filtered(lambda d: d.l10n_do_ncf_type not in ya_existentes)

        for doc in nuevos:
            self.env["l10n_do.account.journal.document_type"].sudo().create({
                "journal_id": self.id,
                "l10n_latam_document_type_id": doc.id,
            })

    @api.model_create_multi
    def create(self, vals_list):
        diarios = super().create(vals_list)
        for diario in diarios:
            diario._l10n_do_create_document_types()
        return diarios

    def write(self, vals):
        campos_clave = {"type", "l10n_latam_use_documents"}
        resultado = super().write(vals)
        if campos_clave.intersection(vals.keys()):
            for diario in self:
                diario._l10n_do_create_document_types()
        return resultado


class AccountJournalDocumentType(models.Model):
    _name = "l10n_do.account.journal.document_type"
    _description = "Tipo de documento fiscal por diario"

    journal_id = fields.Many2one(
        "account.journal", string="Diario", required=True, readonly=True
    )

    l10n_latam_document_type_id = fields.Many2one(
        'l10n_latam.document.type',
        string='Tipo de Comprobante Fiscal (NCF)',
        domain="[('country_id.code', '=', 'DO')]"
    )

    l10n_do_ncf_expiration_date = fields.Date(
        string="Fecha de vencimiento",
        required=True,
        default=lambda self: fields.Date.end_of(
            fields.Date.today().replace(month=12, year=fields.Date.today().year + 1),
            "year"
        ),
    )

    company_id = fields.Many2one(
        string="Compañía", related="journal_id.company_id", readonly=True
    )
