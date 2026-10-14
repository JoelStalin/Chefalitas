from odoo.tests import tagged

from .common import L10nDOTestsCommon


@tagged("-at_install", "post_install")
class TestEcfEnabledFlag(L10nDOTestsCommon):
    """The partner switch decides whether the company issues e-CF (series E) or NCF (series B)."""

    def _sale_journal(self):
        return self.env["account.journal"].search(
            [("company_id", "=", self.do_company.id), ("type", "=", "sale")], limit=1)

    def test_off_by_default_for_new_companies(self):
        partner = self.env["res.partner"].create({"name": "Nueva SRL", "is_company": True})
        self.assertFalse(partner.l10n_do_ecf_enabled)

    def test_partner_switch_drives_company_issuer(self):
        self.do_company.partner_id.l10n_do_ecf_enabled = False
        self.assertFalse(self.do_company.l10n_do_ecf_issuer)
        self.assertEqual(self._sale_journal()._get_journal_codes(), ["B"])
        self.do_company.partner_id.l10n_do_ecf_enabled = True
        self.assertTrue(self.do_company.l10n_do_ecf_issuer)
        self.assertEqual(self._sale_journal()._get_journal_codes(), ["E"])

    def test_company_flag_writes_back_to_partner(self):
        self.do_company.l10n_do_ecf_issuer = True
        self.assertTrue(self.do_company.partner_id.l10n_do_ecf_enabled)
        self.do_company.l10n_do_ecf_issuer = False
        self.assertFalse(self.do_company.partner_id.l10n_do_ecf_enabled)

    def test_switch_changes_are_tracked(self):
        field = self.env["res.partner"]._fields["l10n_do_ecf_enabled"]
        self.assertTrue(field.tracking)
        self.assertTrue(hasattr(self.env["res.partner"], "message_post"))

    def test_disabled_company_does_not_use_easycount(self):
        self.do_company.partner_id.l10n_do_ecf_enabled = False
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.do_company.partner_id.id,
            "company_id": self.do_company.id,
            "journal_id": self._sale_journal().id,
        })
        self.assertFalse(invoice._l10n_do_uses_easycount())
