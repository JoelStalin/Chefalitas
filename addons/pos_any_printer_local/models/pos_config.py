# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    enable_local_printing = fields.Boolean(
        string="Activar impresión local (Agente Windows)",
        help=(
            "Habilita la comunicación con el agente de impresión local "
            "para impresiones directas desde el POS."
        ),
        default=lambda self: self._get_default_enable_local_printing(),
    )

    # Caja (recibo)
    local_cashier_printer_name = fields.Char(
        string="Impresora local (Caja)",
        help="Nombre EXACTO de la impresora en Windows (Panel de control > Impresoras).",
        default=lambda self: self._get_default_cashier_printer_name(),
    )

    # Cocina (comandas) — usado por impresoras de pedido / order printers
    local_kitchen_printer_name = fields.Char(
        string="Impresora local (Cocina)",
        help="Nombre EXACTO de la impresora de cocina en Windows.",
        default=lambda self: self._get_default_kitchen_printer_name(),
    )

    # Retro-compatibilidad con versiones previas del módulo
    local_printer_name = fields.Char(
        string="(DEPRECADO) Impresora local",
        help="Campo legado. Se mantiene por compatibilidad; use 'Impresora local (Caja)'.",
        compute="_compute_local_printer_name",
        inverse="_inverse_local_printer_name",
        store=True,
        readonly=False,
    )

    agent_url = fields.Char(
        string="URL del agente local",
        help="Dirección base del agente local (ej.: http://127.0.0.1:9060 o https://PC:9060).",
        default=lambda self: self._get_default_agent_url(),
    )

    @api.depends("local_cashier_printer_name")
    def _compute_local_printer_name(self):
        for rec in self:
            rec.local_printer_name = rec.local_cashier_printer_name or ""

    def _inverse_local_printer_name(self):
        for rec in self:
            # Si alguien escribe el campo legado, lo reflejamos en 'caja'
            rec.local_cashier_printer_name = rec.local_printer_name or ""

    # ---------- Defaults desde parámetros del sistema ----------
    @api.model
    def _get_default_enable_local_printing(self):
        icp = self.env["ir.config_parameter"].sudo()
        return icp.get_param("pos_any_printer_local.pos_enable_local_printing", "False") in ("True", "1", True)

    @api.model
    def _get_default_cashier_printer_name(self):
        icp = self.env["ir.config_parameter"].sudo()
        # Compat: si solo existía pos_local_printer_name, úsalo como caja
        return icp.get_param("pos_any_printer_local.pos_local_cashier_printer_name",
                             icp.get_param("pos_any_printer_local.pos_local_printer_name", ""))

    @api.model
    def _get_default_kitchen_printer_name(self):
        icp = self.env["ir.config_parameter"].sudo()
        return icp.get_param("pos_any_printer_local.pos_local_kitchen_printer_name", "")

    @api.model
    def _get_default_agent_url(self):
        icp = self.env["ir.config_parameter"].sudo()
        return icp.get_param("pos_any_printer_local.pos_agent_url", "http://127.0.0.1:9060")


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_enable_local_printing = fields.Boolean(
        string="TPV: habilitar impresión local por defecto",
        help="Valor por defecto aplicado al crear nuevos TPV (pos.config).",
        config_parameter="pos_any_printer_local.pos_enable_local_printing",
        default=False,
    )

    pos_local_cashier_printer_name = fields.Char(
        string="TPV: impresora por defecto (Caja)",
        help="Se guarda como parámetro de sistema para reutilizarlo en nuevos TPV.",
        config_parameter="pos_any_printer_local.pos_local_cashier_printer_name",
    )

    pos_local_kitchen_printer_name = fields.Char(
        string="TPV: impresora por defecto (Cocina)",
        help="Se guarda como parámetro de sistema para reutilizarlo en nuevos TPV.",
        config_parameter="pos_any_printer_local.pos_local_kitchen_printer_name",
    )

    pos_agent_url = fields.Char(
        string="TPV: URL por defecto del agente",
        help="Se guarda como parámetro de sistema para reutilizarlo en nuevos TPV.",
        config_parameter="pos_any_printer_local.pos_agent_url",
        default="http://127.0.0.1:9060",
    )
