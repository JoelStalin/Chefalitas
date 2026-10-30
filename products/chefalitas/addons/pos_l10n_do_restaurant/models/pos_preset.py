from odoo import api, models

# preset xmlid -> DO chart fiscal position (account.chart.template ref)
DO_RESTAURANT_PRESETS = {
    "pos_restaurant.pos_takein_preset": "position_restaurant",  # ITBIS + propina legal
    "pos_restaurant.pos_takeout_preset": "position_restaurant_takeout",  # solo ITBIS
    "pos_restaurant.pos_delivery_preset": "position_restaurant_takeout",  # no es consumo en el local
}


class PosPreset(models.Model):
    _inherit = "pos.preset"

    @api.model
    def _l10n_do_apply_restaurant_fiscal_positions(self, company=None):
        """Set the DGII restaurant fiscal positions on the restaurant presets.

        Presets are not company-dependent in Odoo 20, so the first Dominican company is used
        unless one is given. Presets that already have a fiscal position are left untouched.
        """
        company = company or self.env["res.company"].search(
            [("account_fiscal_country_id.code", "=", "DO")], limit=1)
        if not company:
            return False
        chart = self.env["account.chart.template"].with_company(company)
        for preset_xmlid, position_ref in DO_RESTAURANT_PRESETS.items():
            preset = self.env.ref(preset_xmlid, raise_if_not_found=False)
            position = chart.ref(position_ref, raise_if_not_found=False)
            if preset and position and not preset.fiscal_position_id:
                preset.fiscal_position_id = position
        return True
