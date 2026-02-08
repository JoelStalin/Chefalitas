# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


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
    print_device_id = fields.Many2one(
        "pos.print.device",
        string="Local Agent Device",
        help="Device record that contains the per-installation token.",
    )
    local_printer_cashier_name = fields.Char(string="Printer (Cashier)")
    local_printer_kitchen_name = fields.Char(string="Printer (Kitchen)")
    local_printer_print_as_image = fields.Boolean(default=False)
    local_printer_image_width = fields.Integer(default=576)
    any_printer_ip = fields.Char(
        string="HW Proxy IP (legacy)",
        help="Only used when printing_mode is HW Proxy.",
        default="127.0.0.1:8069",
    )
    local_agent_token = fields.Char(
        compute="_compute_local_agent_token",
        help="Token for Local Agent; only set when device is active (for POS UI).",
    )
    printing_suite_allowed = fields.Boolean(
        compute="_compute_printing_suite_allowed",
        help="True when the user is allowed to use the Printing Suite and mode is enabled.",
    )

    @api.depends("print_device_id", "print_device_id.state", "print_device_id.token")
    @api.depends_context("uid")
    def _compute_local_agent_token(self):
        for rec in self:
            if not rec._is_printing_suite_allowed():
                rec.local_agent_token = None
            elif rec.printing_mode != "local_agent":
                rec.local_agent_token = None
            elif rec.print_device_id and rec.print_device_id.state == "active":
                rec.local_agent_token = rec.print_device_id.token
            else:
                rec.local_agent_token = None

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
            "print_device_id",
            "local_agent_token",
            "printing_suite_allowed",
            "local_printer_cashier_name",
            "local_printer_kitchen_name",
            "local_printer_print_as_image",
            "local_printer_image_width",
            "any_printer_ip",
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
            "print_device_id",
            "local_agent_token",
            "printing_suite_allowed",
            "local_printer_cashier_name",
            "local_printer_kitchen_name",
            "local_printer_print_as_image",
            "local_printer_image_width",
            "any_printer_ip",
        ]
        for f in extras:
            if f not in fields:
                fields.append(f)
        return fields

    @api.constrains("printing_mode", "print_device_id")
    def _check_printing_mode_device(self):
        for rec in self:
            if rec.printing_mode == "local_agent" and not rec.print_device_id:
                raise ValidationError(_("Local Agent mode requires a Local Agent Device."))
            if rec.print_device_id and rec.print_device_id.pos_config_id != rec:
                raise ValidationError(
                    _("Selected Local Agent Device is linked to another POS config.")
                )
