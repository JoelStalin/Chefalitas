# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PosConfig(models.Model):
    _inherit = "pos.config"

    printing_mode = fields.Selection(
        [
            ("local_agent", "Local Agent (Windows)"),
            ("hw_proxy", "HW Proxy / Any Printer"),
        ],
        default="local_agent",
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
    )
    local_agent_token = fields.Char(
        compute="_compute_local_agent_token",
        help="Token for Local Agent; only set when device is active (for POS UI).",
    )

    @api.depends("print_device_id", "print_device_id.state", "print_device_id.token")
    def _compute_local_agent_token(self):
        for rec in self:
            if rec.print_device_id and rec.print_device_id.state == "active":
                rec.local_agent_token = rec.print_device_id.token
            else:
                rec.local_agent_token = None

    def _loader_params_pos_config(self):
        params = super()._loader_params_pos_config()
        params["fields"].extend([
            "printing_mode",
            "print_device_id",
            "local_agent_token",
            "local_printer_cashier_name",
            "local_printer_kitchen_name",
            "local_printer_print_as_image",
            "local_printer_image_width",
            "any_printer_ip",
        ])
        return params

    @api.constrains("printing_mode", "print_device_id")
    def _check_printing_mode_device(self):
        for rec in self:
            if rec.printing_mode == "local_agent" and not rec.print_device_id:
                raise ValidationError(_("Local Agent mode requires a Local Agent Device."))
            if rec.print_device_id and rec.print_device_id.pos_config_id != rec:
                raise ValidationError(
                    _("Selected Local Agent Device is linked to another POS config.")
                )
