from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestDoRestaurantTaxes(AccountTestInvoicingCommon):
    """Dine-in: ITBIS 18% + 10% legal tip on the consumption subtotal; takeout/delivery: ITBIS only."""

    @classmethod
    @AccountTestInvoicingCommon.setup_country("do")
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        chart = cls.env["account.chart.template"].with_company(cls.company)
        cls.dine_in = chart.ref("position_restaurant")
        cls.takeout = chart.ref("position_restaurant_takeout")
        cls.itbis_18 = chart.ref("tax_18_sale")
        cls.restaurant = chart.ref("tax_group_restaurant_sale")
        # presets are POS configuration (POS manager rights); the install hook runs as superuser
        for xmlid in ("pos_restaurant.pos_takein_preset", "pos_restaurant.pos_takeout_preset",
                      "pos_restaurant.pos_delivery_preset"):
            cls.env.ref(xmlid).sudo().fiscal_position_id = False
        cls.env["pos.preset"].sudo()._l10n_do_apply_restaurant_fiscal_positions(cls.company)

    def _total(self, taxes, amount=820.0):
        res = taxes.compute_all(amount, currency=self.company.currency_id)
        return res["total_included"], sorted(round(t["amount"], 2) for t in res["taxes"])

    def _preset(self, xmlid):
        return self.env.ref(xmlid).sudo()  # POS configuration records

    def test_presets_get_dgii_fiscal_positions(self):
        self.assertEqual(self._preset("pos_restaurant.pos_takein_preset").fiscal_position_id, self.dine_in)
        self.assertEqual(self._preset("pos_restaurant.pos_takeout_preset").fiscal_position_id, self.takeout)
        self.assertEqual(self._preset("pos_restaurant.pos_delivery_preset").fiscal_position_id, self.takeout)

    def test_dine_in_adds_legal_tip_outside_itbis_base(self):
        taxes = self.dine_in.map_tax(self.itbis_18)
        self.assertEqual(taxes, self.restaurant)
        # 820 consumo + 147.60 ITBIS (18% de 820) + 82.00 propina (10% de 820)
        self.assertEqual(self._total(taxes), (1049.6, [82.0, 147.6]))

    def test_takeout_is_itbis_only(self):
        # Products carry 18% ITBIS: dine-in maps it to the Restaurant group, takeout keeps it.
        taxes = self.takeout.map_tax(self.itbis_18)
        self.assertEqual(taxes, self.itbis_18)
        self.assertEqual(self._total(taxes), (967.6, [147.6]))

    def test_products_must_not_carry_the_restaurant_group(self):
        # Odoo 20 l10n_do data: in "Para Llevar" the Restaurant group is replaced by 18%, 16%
        # AND 0% ITBIS (all three declare it as original tax). Products must therefore carry
        # the 18% ITBIS and let the dine-in fiscal position add the legal tip.
        self.assertGreater(len(self.takeout.map_tax(self.restaurant)), 1)

    def test_existing_preset_configuration_is_kept(self):
        preset = self._preset("pos_restaurant.pos_takeout_preset")
        preset.fiscal_position_id = self.dine_in
        self.env["pos.preset"].sudo()._l10n_do_apply_restaurant_fiscal_positions(self.company)
        self.assertEqual(preset.fiscal_position_id, self.dine_in)
