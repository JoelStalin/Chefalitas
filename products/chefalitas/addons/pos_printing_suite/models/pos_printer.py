# -*- coding: utf-8 -*-
import secrets

from odoo import api, fields, models


class PosPrinter(models.Model):
    _inherit = "pos.printer"

    @api.model
    def _load_pos_data_fields(self, config_id):
        parent = getattr(super(), "_load_pos_data_fields", None)
        result = parent(config_id) if callable(parent) else []
        if result is None:
            result = []
        extras = ["printer_type", "local_printer_name", "hw_proxy_ip"]
        for f in extras:
            if f not in result:
                result.append(f)
        return result

    printer_type = fields.Selection(
        selection_add=[
            ("local_agent", "Local Agent (Windows)"),
            ("hw_proxy_any_printer", "HW Proxy / Any Printer"),
            ("cloud_gateway", "Gateway / túnel (Odoo en la nube)"),
        ],
        ondelete={
            "local_agent": "set default",
            "hw_proxy_any_printer": "set default",
            "cloud_gateway": "set default",
        },
    )
    hw_proxy_ip = fields.Char(string="IP de la impresora o del agente",
                              help="Network printer (raw TCP) or local agent IP. The network discovery fills it.")
    local_printer_name = fields.Char(string="Windows Printer Name")
    network_port = fields.Integer(string="Puerto", help="Empty: 9100 for a network printer, 8085 for the local agent.")
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, index=True)
    gateway_token = fields.Char(copy=False, readonly=True, groups="base.group_system",
                                help="Secret of the cloud gateway or the local agent; the gateway sends it to pull jobs.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("gateway_token", secrets.token_urlsafe(32))
        return super().create(vals_list)

    def action_rotate_gateway_token(self):
        for printer in self:
            printer.gateway_token = secrets.token_urlsafe(32)

    def _printing_connection(self):
        """How server-side jobs reach this printer: direct (raw TCP), agent (HTTP) or gateway (pulled); None otherwise."""
        self.ensure_one()
        return {"hw_proxy_any_printer": "direct", "local_agent": "agent", "cloud_gateway": "gateway"}.get(self.printer_type)

    def _printing_host(self):
        self.ensure_one()
        return self.hw_proxy_ip or self.printer_ip
