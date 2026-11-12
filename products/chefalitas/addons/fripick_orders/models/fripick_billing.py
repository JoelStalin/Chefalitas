import logging

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

from .compat import param_int

_logger = logging.getLogger(__name__)


class FripickBilling(models.AbstractModel):
    """Monthly invoice on the 1st: one invoice per company for last month's captured orders. The company flag decides
    who issues it; posting assigns the fiscal voucher (e-CF through l10n_do_accounting when installed)."""
    _name = "fripick.billing"
    _description = "Fripick monthly billing"

    @api.model
    def _period(self, today=None):
        today = today or fields.Date.context_today(self)
        end = today.replace(day=1)
        return end - relativedelta(months=1), end

    @api.model
    def run(self, today=None):
        start, end = self._period(today)
        Order = self.env["fripick.order"].sudo()
        fripick_company_id = param_int(self.env, "fripick.company_id")
        created = self.env["account.move"]
        for company in self.env["res.company"].sudo().search([]):
            orders = Order.search([
                ("company_id", "=", company.id), ("invoice_id", "=", False),
                ("closed_at", ">=", fields.Datetime.to_datetime(start)), ("closed_at", "<", fields.Datetime.to_datetime(end)),
            ])
            if not orders or not company.fripick_partner_id:
                continue
            if company.fripick_invoice_issuer == "fripick":
                if not fripick_company_id:
                    _logger.warning("Fripick billing: fripick.company_id is not set; %s skipped", company.name)
                    continue
                issuer, partner = self.env["res.company"].browse(fripick_company_id), company.partner_id
            else:
                issuer, partner = company, company.fripick_partner_id
            move = self.env["account.move"].with_company(issuer).sudo().create({
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_date": end,
                "company_id": issuer.id,
                "invoice_origin": f"Fripick {start:%Y-%m}",
                "invoice_line_ids": [(0, 0, {
                    "name": f"Pedidos Fripick {start:%m/%Y}: {len(orders)} órdenes",
                    "quantity": 1,
                    "price_unit": sum(orders.mapped("amount_total")),
                })],
            })
            orders.write({"invoice_id": move.id})
            try:
                move.action_post()
            except Exception as exc:  # e.g. fiscal sequence missing: the draft waits for a person, nothing is lost
                _logger.warning("Fripick invoice %s left in draft: %s", move.id, exc)
            created |= move
        return created

    @api.model
    def _cron_monthly(self):
        if fields.Date.context_today(self).day == 1:
            return self.run()
        return self.env["account.move"]
