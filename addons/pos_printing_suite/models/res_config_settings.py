# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    printing_mode = fields.Selection(related="pos_config_id.printing_mode", readonly=False)
    local_printer_cashier_name = fields.Char(related="pos_config_id.local_printer_cashier_name", readonly=False)
    local_printer_kitchen_name = fields.Char(related="pos_config_id.local_printer_kitchen_name", readonly=False)
    local_agent_host = fields.Char(related="pos_config_id.local_agent_host", readonly=False)
    local_agent_port = fields.Integer(related="pos_config_id.local_agent_port", readonly=False)
    any_printer_ip = fields.Char(related="pos_config_id.any_printer_ip", readonly=False)
    any_printer_port = fields.Integer(related="pos_config_id.any_printer_port", readonly=False)
