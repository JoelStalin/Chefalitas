import importlib.util

from odoo.modules.module import get_module_path
from odoo.tests import tagged

from . import common


def _load_migration():
    path = get_module_path("l10n_do_accounting") + "/migrations/20.0.1.0.0/post-migrate.py"
    spec = importlib.util.spec_from_file_location("l10n_do_accounting_post_migrate_20", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@tagged("-at_install", "post_install")
class L10nDoAdoptionTest(common.L10nDOTestsCommon):

    def test_single_e31_document_type(self):
        e31 = self.env["l10n_latam.document.type"].search(
            [("doc_code_prefix", "=", "E31"), ("country_id.code", "=", "DO")])
        self.assertEqual(e31, self.env.ref("l10n_do.ecf_31"))
        self.assertEqual(e31.l10n_do_ncf_type, "e-fiscal")

    def test_purchase_type_follows_expense_type(self):
        bill = self._create_l10n_do_invoice(
            data={"document_number": "B0100000091", "expense_type": "02"}, invoice_type="in_invoice")
        self.assertEqual(bill.l10n_do_purchase_type, "2")

    def test_migration_merges_duplicate_document_type(self):
        official = self.env.ref("l10n_do.ecf_31")
        duplicate = official.copy({"name": "E31 duplicate (pre-20)"})
        self.env["ir.model.data"].create({
            "module": "l10n_do_accounting", "name": "ecf_fiscal_client",
            "model": "l10n_latam.document.type", "res_id": duplicate.id,
        })
        self.do_company.l10n_do_ecf_issuer = True
        invoice = self._create_l10n_do_invoice(data={"document_number": "E310000000091"})
        self.env.cr.execute("UPDATE account_move SET l10n_latam_document_type_id = %s WHERE id = %s",
                            (duplicate.id, invoice.id))
        self.env.invalidate_all()
        _load_migration().merge_document_types(self.env.cr)
        self.env.invalidate_all()
        self.assertEqual(invoice.l10n_latam_document_type_id, official)
        self.assertFalse(duplicate.exists())
