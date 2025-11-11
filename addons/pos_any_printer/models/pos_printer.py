# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

class PosPrinter(models.Model):

    _inherit = 'pos.printer'

    printer_type = fields.Selection(
        selection_add=[("any_printer", "Usar cualquier impresora")]
    )
    any_printer_ip = fields.Char(
        string="Dirección IP de la impresora proxy",
        help="Dirección IP local de la impresora de recibos.",
    )

    @api.constrains('any_printer_ip')
    def _constrains_any_printer_ip(self):
        for record in self:
            if record.printer_type == 'any_epos' and not record.any_printer_ip:
                raise ValidationError(_("La dirección IP de la impresora no puede estar vacía."))

    @api.model
    def _load_pos_data_fields(self, config_id):
        params = super()._load_pos_data_fields(config_id)
        params += ['name']
        params += ['any_printer_ip']
        return params
