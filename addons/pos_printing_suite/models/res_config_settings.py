# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Placeholder for global printing suite defaults if needed later.
    # Legacy pos_any_printer_local used config_parameter; we keep config on pos.config only.
    pass
