from . import common
from odoo.tests import tagged
from odoo.exceptions import RedirectWarning


@tagged("-at_install", "post_install")
class AccountJournalTest(common.L10nDOTestsCommon):
    def test_001_raise_redirect(self):
        """
        Checks Journal raises RedirectWarning if trying to
        setup fiscal journal without company vat
        """

        journal = self.env["account.journal"].search(
            [
                ("type", "=", "sale"),
                ("company_id", "=", self.do_company.id),
            ],
            limit=1,
        )

        with self.assertRaises(RedirectWarning):
            self.do_company.vat = False
            journal._get_journal_ncf_types()

    def test_002_deleting_a_journal_removes_its_document_types(self):
        """Live finding: the NOT NULL journal_id without ondelete blocked deleting journals (chart switch)."""
        journal = self.env["account.journal"].create({
            "name": "Ventas temporales", "code": "VTMP", "type": "sale",
            "company_id": self.do_company.id, "l10n_latam_use_documents": True,
        })
        doc_types = journal.l10n_do_document_type_ids
        self.assertTrue(doc_types)
        journal.unlink()
        self.assertFalse(doc_types.exists())
