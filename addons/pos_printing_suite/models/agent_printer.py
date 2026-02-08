# -*- coding: utf-8 -*-
from odoo import fields, models


class PosPrintingAgentPrinter(models.Model):
    _name = "pos.printing.agent.printer"
    _description = "POS Printing Agent Printer"
    _rec_name = "name"
    _order = "name"

    name = fields.Char(required=True)
    pos_config_id = fields.Many2one("pos.config", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="pos_config_id.company_id", store=True, readonly=True)
    last_seen = fields.Datetime()

    _sql_constraints = [
        ("agent_printer_unique", "unique(pos_config_id, name)", "Printer must be unique per POS."),
    ]
