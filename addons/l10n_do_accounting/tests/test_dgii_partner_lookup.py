from unittest.mock import patch

from odoo.tests import tagged

from .common import L10nDOTestsCommon
from ..models import res_partner as partner_module

DGII_INFO = {
    "name": "EMPRESA DE PRUEBA SRL", "commercial_name": "PRUEBA", "formatted_rnc": "1-31-00000-0",
    "status": "ACTIVO", "regime": "NORMAL", "economic_activity": "SERVICIOS", "local_admin": "ADM LOCAL",
    "electronic_billing": False,
}


@tagged("-at_install", "post_install")
class TestDgiiPartnerLookup(L10nDOTestsCommon):
    """DGII lookup and RNC check digit. The DGII is never contacted: the query is mocked."""

    def test_checksum(self):
        ok, kind, _ = partner_module._validate_dominican_vat_checksum("133136122")
        self.assertEqual(kind, "RNC")
        self.assertTrue(ok)
        bad = "13313612" + str((int("2") + 1) % 10)
        self.assertFalse(partner_module._validate_dominican_vat_checksum(bad)[0])
        self.assertEqual(partner_module._validate_dominican_vat_checksum("123")[1], "Desconocido")

    def test_invalid_check_digit_warns_on_form(self):
        partner = self.env["res.partner"].new({"name": "Cliente", "vat": "131000001"})
        result = partner._onchange_l10n_do_vat()
        self.assertEqual(result["warning"]["title"], "RNC / Cédula Inválido")
        self.assertFalse(self.env["res.partner"].new({"name": "Ok", "vat": "133136122"})._onchange_l10n_do_vat())

    def test_consult_keeps_name_and_notes(self):
        partner = self.env["res.partner"].create({
            "name": "Nombre del usuario", "vat": "133136122", "comment": "Nota existente",
            "country_id": self.env.ref("base.do").id})
        with patch.object(partner_module, "query_dgii_by_rnc_standalone", return_value=DGII_INFO) as query:
            partner.action_dgii_consult()
        query.assert_called_once_with("133136122")
        self.assertEqual(partner.name, "Nombre del usuario")
        self.assertIn("Nota existente", partner.comment)
        self.assertIn("ACTIVO", partner.comment)
        self.assertEqual(partner.l10n_do_tax_regime, "NORMAL")

    def test_no_network_on_save(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("network call")):
            partner = self.env["res.partner"].create({"name": "Sin red", "vat": "133136122",
                                                      "country_id": self.env.ref("base.do").id})
            partner.write({"name": "Sin red SRL"})
