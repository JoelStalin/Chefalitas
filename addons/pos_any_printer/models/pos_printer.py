# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

class PosPrinter(models.Model):

    _inherit = 'pos.printer'

    printer_type = fields.Selection(selection_add=[('any_printer', 'Use any printer')])
    any_printer_ip = fields.Char(string='Proxy Printer IP Address', help="Local IP address of proxy receipt printer.")

    @api.constrains('any_printer_ip')
    def _constrains_any_printer_ip(self):
        for record in self:
            if record.printer_type == 'any_epos' and not record.any_printer_ip:
                raise ValidationError(_("any Printer IP Address cannot be empty."))

    @api.model
    def _load_pos_data_fields(self, config_id):
        params = super()._load_pos_data_fields(config_id)
        params += ['name']
        params += ['any_printer_ip']
        return params
