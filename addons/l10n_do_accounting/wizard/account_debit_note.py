from odoo import _, api, fields, models
from odoo.exceptions import UserError, AccessError


class AccountDebitNote(models.TransientModel):
    _inherit = "account.debit.note"

    @api.model
    def _get_l10n_do_debit_type_selection(self):
        selection = [
            ("percentage", _("Porcentaje")),
            ("fixed_amount", _("Monto")),
        ]
        return selection

    @api.model
    def _get_l10n_do_default_debit_type(self):
        return "percentage"

    @api.model
    def _get_l10n_do_debit_action_selection(self):
        return [
            ("draft_debit", _("Crear borrador de nota de débito")),
            ("apply_debit", _("Aplicar nota de débito")),
        ]

    l10n_latam_country_code = fields.Char(
        default=lambda self: self.env.company.country_code,
        help="Campo técnico para mostrar u ocultar campos según la localización.",
    )
    l10n_do_debit_type = fields.Selection(
        selection=_get_l10n_do_debit_type_selection,
        default=_get_l10n_do_default_debit_type,
        string="Tipo de débito",
    )
    l10n_do_debit_action = fields.Selection(
        selection=_get_l10n_do_debit_action_selection,
        default="draft_debit",
        string="Acción",
    )
    l10n_do_percentage = fields.Float(
        help="Nota de débito basada en el porcentaje de la factura de origen.",
        string="Porcentaje",
    )
    l10n_do_amount = fields.Float(
        help="Nota de débito basada en un monto fijo.",
        string="Monto",
    )
    l10n_do_account_id = fields.Many2one(
        "account.account",
        string="Cuenta",
        domain=[("deprecated", "=", False)],
    )
    l10n_latam_document_number = fields.Char(
        string="Número de documento",
    )
    l10n_do_ecf_modification_code = fields.Selection(
        selection=lambda self: self.env[
            "account.move"
        ]._get_l10n_do_ecf_modification_code(),
        string="Código de modificación e-CF",
        copy=False,
    )
    is_ecf_invoice = fields.Boolean(
        string="Es factura electrónica",
    )
    l10n_latam_use_documents = fields.Boolean("Usa documentos", readonly=True)
    l10n_latam_document_type_id = fields.Many2one(
        "l10n_latam.document.type", "Tipo de documento", ondelete="cascade"
    )

    @api.model
    def default_get(self, fields):
        res = super(AccountDebitNote, self).default_get(fields)

        move_ids = (
            self.env["account.move"].browse(self.env.context["active_ids"])
            if self.env.context.get("active_model") == "account.move"
            else self.env["account.move"]
        )

        if not move_ids:
            raise UserError(_("No se encontró factura para esta operación."))

        move_ids_use_document = move_ids.filtered(
            lambda move: move.l10n_latam_use_documents
            and move.company_id.country_code == "DO"
        )
        if move_ids_use_document and not self.env.user.has_group(
            "l10n_do_accounting.group_l10n_do_debit_note"
        ):
            raise AccessError(_("No tienes permiso para emitir notas de débito."))

        # Setting default account
        journal = move_ids[0].journal_id
        res["l10n_do_account_id"] = journal.default_account_id.id
        res["l10n_latam_use_documents"] = journal.l10n_latam_use_documents

        # Do not allow Debit Notes if Comprobante de Compra or Gastos Menores
        if move_ids[0].l10n_latam_document_type_id.l10n_do_ncf_type in (
            "informal",
            "minor",
            "e-informal",
            "e-minor",
        ):
            raise UserError(
                _("No puedes emitir notas de crédito/débito para el tipo de documento %s")
                % move_ids_use_document.l10n_latam_document_type_id.name
            )

        if len(move_ids_use_document) > 1:
            raise UserError(
                _("No puedes crear notas de débito para múltiples documentos a la vez.")
            )
        else:
            res["is_ecf_invoice"] = (
                move_ids_use_document and move_ids_use_document[0].is_ecf_invoice
            )

        return res

    @api.onchange("move_ids")
    def _onchange_move_id(self):
        if (
            self.move_ids
            and self.move_ids[0].l10n_latam_use_documents
            and self.l10n_latam_country_code == "DO"
        ):
            move_id = self.move_ids[0]
            move_type = "out_invoice" if move_id.is_sale_document() else "in_invoice"
            move = (
                self.env["account.move"]
                .with_context(internal_type="debit_note")
                .new(
                    {
                        "partner_id": move_id.partner_id.id,
                        "move_type": move_type,
                        "journal_id": move_id.journal_id.id,
                    }
                )
            )
            domain_ids = (
                self.env["l10n_latam.document.type"]
                .search(move._get_l10n_latam_documents_domain())
                .ids
            )
            self.l10n_latam_document_type_id = domain_ids[0]
            return {
                "domain": {
                    "l10n_latam_document_type_id": [
                        (
                            "id",
                            "in",
                            domain_ids,
                        )
                    ]
                }
            }

    def _prepare_default_values(self, move):
        res = super(AccountDebitNote, self)._prepare_default_values(move)

        # Include additional info when l10n_do debit note
        if self.l10n_latam_country_code == "DO" and move.l10n_latam_use_documents:
            res.update(
                dict(
                    l10n_latam_document_type_id=self.l10n_latam_document_type_id.id,
                    l10n_do_ecf_modification_code=self.l10n_do_ecf_modification_code,
                    l10n_latam_document_number=self.l10n_latam_document_number,
                    l10n_do_origin_ncf=move.l10n_latam_document_number,
                    l10n_do_expense_type=move.l10n_do_expense_type,
                    l10n_do_income_type=move.l10n_do_income_type,
                    invoice_origin=move.name,
                    line_ids=[(5, 0, 0)],
                    l10n_do_fiscal_number=move.name,
                )
            )

            origin_invoice_id = self.move_ids or self.env["account.move"].browse(
                self.env.context.get("active_ids")
            )
            taxes = (
                [
                    (
                        6,
                        0,
                        [origin_invoice_id._get_debit_line_tax(res["invoice_date"]).id],
                    )
                ]
                if self.l10n_do_debit_type
                else [(5, 0)]
            )
            price_unit = (
                self.l10n_do_amount
                if self.l10n_do_debit_type == "fixed_amount"
                else origin_invoice_id.amount_untaxed * (self.l10n_do_percentage / 100)
            )
            res["invoice_line_ids"] = [
                (
                    0,
                    0,
                    {
                        "name": self.reason or _("Débito"),
                        "price_unit": price_unit,
                        "quantity": 1,
                        "tax_ids": taxes,
                    },
                )
            ]

        return res

    def create_debit(self):
        action = super(AccountDebitNote, self).create_debit()
        if self.l10n_do_debit_action == "apply_debit":
            # Post Debit Note
            move_id = self.env["account.move"].browse(action.get("res_id", False))
            move_id._post()

        return action
