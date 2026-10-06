import hashlib

from odoo.tests import TransactionCase, tagged

from odoo.addons.orca_bridge.hooks import LEAKED_TOKEN_SHA256, ensure_api_token


@tagged("post_install", "-at_install")
class TestOrcaApiToken(TransactionCase):

    def _token(self):
        return self.env["ir.config_parameter"].sudo().get_str("orca.api_token") or ""

    def test_install_sets_a_random_non_leaked_token(self):
        token = self._token()
        self.assertGreaterEqual(len(token), 32)
        self.assertNotEqual(hashlib.sha256(token.encode()).hexdigest(), LEAKED_TOKEN_SHA256)

    def test_custom_token_is_kept(self):
        self.env["ir.config_parameter"].sudo().set_str("orca.api_token", "my-own-secret-value-123456789")
        self.assertFalse(ensure_api_token(self.env))
        self.assertEqual(self._token(), "my-own-secret-value-123456789")

    def test_missing_token_is_generated(self):
        self.env["ir.config_parameter"].sudo().set_str("orca.api_token", "")
        self.assertTrue(ensure_api_token(self.env))
        self.assertTrue(self._token())
