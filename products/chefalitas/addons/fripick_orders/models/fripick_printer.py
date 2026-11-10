import secrets

from odoo import api, fields, models


class FripickPrinter(models.Model):
    """A kitchen or cashier printer. Direct: Odoo reaches it on the same network (raw TCP 9100).
    Agent: the POS Printing Suite local agent over HTTP. Gateway: Odoo is in the cloud; the downloadable gateway
    pulls the jobs and prints locally, so no inbound port is opened at the restaurant."""
    _name = "fripick.printer"
    _description = "Fripick printer"

    name = fields.Char(required=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    role = fields.Selection([("kitchen", "Cocina"), ("cashier", "Caja")], required=True, default="kitchen")
    connection = fields.Selection([("direct", "Directa por IP (misma red)"), ("agent", "Agente local (HTTP)"),
                                   ("gateway", "Gateway / túnel (Odoo en la nube)")], required=True, default="direct")
    host = fields.Char(help="IP of the printer (direct) or of the local agent (agent).")
    port = fields.Integer(default=9100)
    agent_printer_name = fields.Char("Nombre en el agente", help="Printer name as the local agent reports it.")
    paper = fields.Selection([("80mm", "Ticket 80 mm"), ("a4", "A4")], default="80mm", required=True)
    token = fields.Char(copy=False, readonly=True, groups="base.group_system",
                        help="Secret of the gateway or agent; the gateway sends it to pull jobs.")
    active = fields.Boolean(default=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("token", secrets.token_urlsafe(32))
        return super().create(vals_list)

    def action_rotate_token(self):
        for printer in self:
            printer.token = secrets.token_urlsafe(32)
