# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


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
        ],
        ondelete={
            "local_agent": "set default",
            "hw_proxy_any_printer": "set default",
        },
    )
    hw_proxy_ip = fields.Char(string="HW Proxy IP (legacy)")
    local_printer_name = fields.Char(string="Windows Printer Name")

    @api.constrains("printer_type", "hw_proxy_ip")
    def _check_hw_proxy_ip(self):
        for p in self:
            if p.printer_type == "hw_proxy_any_printer" and not (p.hw_proxy_ip or "").strip():
                raise ValidationError(
                    _("HW Proxy IP is required for HW Proxy printers.")
                )
