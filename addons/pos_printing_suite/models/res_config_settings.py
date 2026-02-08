# -*- coding: utf-8 -*-
from odoo import models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Keep POS Printing Suite settings only in pos.config.
    pass
