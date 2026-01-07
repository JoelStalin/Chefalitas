# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import  fields, models, api

class PosConfig(models.Model):
    _inherit = 'pos.config'

    any_printer_ip = fields.Char(string='Any Printer IP', help="Local IP address of an Any receipt printer.")
    
  