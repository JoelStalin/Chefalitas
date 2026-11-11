from unittest.mock import patch

from odoo.tests.common import TransactionCase

MOD = "odoo.addons.l10n_do_rnc_autofill.models.res_partner"
INFO = {"rnc": "130610177", "name": "SUPER COLMADO DOMINGO TORRES EIRL", "regime": "NORMAL", "is_company": True}


class TestRncAutofill(TransactionCase):
    def test_solo_rnc_completa_el_nombre(self):
        partner = self.env["res.partner"].new({"vat": "130610177"})
        with patch(MOD + ".query_dgii_by_rnc_standalone", return_value=INFO):
            partner._onchange_rnc_autofill_vat()
        self.assertEqual(partner.name, INFO["name"])
        self.assertTrue(partner.is_company)

    def test_solo_nombre_completa_el_rnc_si_es_unico(self):
        partner = self.env["res.partner"].new({"name": "SUPER COLMADO DOMINGO TORRES"})
        with patch(MOD + ".query_dgii_by_name_standalone", return_value=[INFO]):
            partner._onchange_rnc_autofill_name()
        self.assertEqual(partner.vat, "130610177")
        self.assertEqual(partner.name, INFO["name"])

    def test_nombre_ambiguo_avisa_y_no_completa(self):
        partner = self.env["res.partner"].new({"name": "COLMADO"})
        many = [dict(INFO, rnc="133677784", name="COLMADO 380 SRL"), dict(INFO, rnc="130872333", name="COLMADO 5 Y 10 SRL")]
        with patch(MOD + ".query_dgii_by_name_standalone", return_value=many):
            result = partner._onchange_rnc_autofill_name()
        self.assertFalse(partner.vat)
        self.assertIn("warning", result)

    def test_rnc_invalido_avisa(self):
        partner = self.env["res.partner"].new({"vat": "123456789"})
        result = partner._onchange_rnc_autofill_vat()
        self.assertIn("warning", result)

    def test_contacto_existente_no_se_consulta(self):
        partner = self.env["res.partner"].create({"name": "JUAN PEREZ SUAREZ"})
        with patch(MOD + ".query_dgii_by_name_standalone", side_effect=AssertionError("no debe consultar")):
            partner.name = "JUAN PEREZ SUAREZ X"
            partner._onchange_rnc_autofill_name()
