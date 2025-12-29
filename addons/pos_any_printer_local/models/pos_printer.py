# -*- coding: utf-8 -*-
from odoo import fields, models


class PosPrinter(models.Model):
    _inherit = "pos.printer"

    printer_type = fields.Selection(
        selection_add=[("local_agent", "Agente de impresora local (Windows)")],
        ondelete={"local_agent": "set default"},
    )

    local_printer_name = fields.Char(
        string="Nombre de impresora (Windows)",
        help="Nombre EXACTO de la impresora en Windows.",
    )

    agent_url = fields.Char(
        string="URL del agente",
        help="URL del agente instalado en el equipo que tiene acceso a la impresora.",
    )
