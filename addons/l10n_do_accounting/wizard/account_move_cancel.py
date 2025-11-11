from odoo import _, _lt, fields, models
from odoo.exceptions import UserError


class AccountMoveCancel(models.TransientModel):
    """Este asistente cancela todas las facturas seleccionadas."""

    _name = "account.move.cancel"
    _description = _lt("Cancelar las facturas seleccionadas")

    l10n_do_cancellation_type = fields.Selection(
        selection=lambda self: self.env[
            "account.move"
        ]._get_l10n_do_cancellation_type(),
        string="Tipo de cancelación",
        copy=False,
        required=True,
    )

    def move_cancel(self):
        context = dict(self._context or {})
        active_ids = context.get("active_ids", []) or []
        for invoice in self.env["account.move"].browse(active_ids):
            if invoice.state == "cancel":
                raise UserError(
                    _(
                        "Las facturas seleccionadas no pueden cancelarse porque "
                        "ya están en estado 'Cancelado'."
                    )
                )
            if invoice.payment_state != "not_paid":
                raise UserError(
                    _(
                        "Las facturas seleccionadas no pueden cancelarse porque "
                        "ya están en estado 'Pagado'."
                    )
                )

            # we call button_cancel() so dependency chain is
            # not broken in other modules extending that function
            invoice.mapped("line_ids.analytic_line_ids").unlink()
            invoice.with_context(skip_cancel_wizard=True).button_cancel()
            invoice.l10n_do_cancellation_type = self.l10n_do_cancellation_type

        return {"type": "ir.actions.act_window_close"}
