# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    printing_mode = fields.Selection(
        [
            ("odoo_default", "Odoo (Standard)"),
            ("local_agent", "Local Agent (Windows)"),
            ("hw_proxy", "HW Proxy / Any Printer"),
        ],
        default="odoo_default",
        required=True,
    )
    local_agent_host = fields.Char(
        string="Local Agent IP",
        default="127.0.0.1",
    )
    local_agent_port = fields.Integer(
        string="Local Agent Port",
        default=9060,
    )
    local_printer_cashier_name = fields.Char(string="Printer (Cashier)")
    local_printer_kitchen_name = fields.Char(string="Printer (Kitchen)")
    any_printer_ip = fields.Char(
        string="HW Proxy Host",
        help="Host/IP for HW Proxy when printing_mode is HW Proxy.",
        default="127.0.0.1",
    )
    any_printer_port = fields.Integer(
        string="HW Proxy Port",
        default=8069,
    )
    printing_suite_allowed = fields.Boolean(
        compute="_compute_printing_suite_allowed",
        help="True when the user is allowed to use the Printing Suite and mode is enabled.",
    )

    @api.depends("printing_mode")
    @api.depends_context("uid")
    def _compute_printing_suite_allowed(self):
        for rec in self:
            rec.printing_suite_allowed = rec._is_printing_suite_allowed()

    def _is_printing_suite_allowed(self):
        self.ensure_one()
        if self.printing_mode not in ("local_agent", "hw_proxy"):
            return False
        group = self.env.ref("pos_printing_suite.group_pos_printing_suite_printing", raise_if_not_found=False)
        if not group:
            return False
        return group in self.env.user.groups_id

    def _loader_params_pos_config(self):
        parent = getattr(super(), "_loader_params_pos_config", None)
        params = parent() if callable(parent) else {"fields": []}
        params["fields"].extend([
            "printing_mode",
            "printing_suite_allowed",
            "local_agent_host",
            "local_agent_port",
            "local_printer_cashier_name",
            "local_printer_kitchen_name",
            "any_printer_ip",
            "any_printer_port",
        ])
        return params

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields = super()._load_pos_data_fields(config_id)
        # If fields is falsy, the base loader will load all fields; keep that behavior.
        if not fields:
            return fields
        extras = [
            "printing_mode",
            "printing_suite_allowed",
            "local_agent_host",
            "local_agent_port",
            "local_printer_cashier_name",
            "local_printer_kitchen_name",
            "any_printer_ip",
            "any_printer_port",
        ]
        for f in extras:
            if f not in fields:
                fields.append(f)
        return fields

    # NOTE: no device/token required; printing suite is configured by printer names only.
