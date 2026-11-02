from odoo.tests import TransactionCase, tagged

from odoo.addons.pos_printing_suite.models.pos_config import get_module_resource


@tagged("post_install", "-at_install")
class TestAgentInstaller(TransactionCase):
    """Odoo 20 runtime APIs used by the agent installer: module paths and raw attachments."""

    def test_module_paths_resolve_or_false(self):
        self.assertTrue(get_module_resource("pos_printing_suite", "agent_src", "local_printer_agent"))
        self.assertFalse(get_module_resource("pos_printing_suite", "does", "not", "exist"))

    def test_build_installer_creates_raw_attachment(self):
        config = self.env["pos.config"].create({"name": "Printing test"})
        config._build_agent_installer()
        artifact = config.agent_artifact_id
        self.assertTrue(artifact, "installer attachment created")
        self.assertTrue(artifact.raw and artifact.raw.content, "attachment has content")
        self.assertIn(artifact.mimetype, ("application/x-msi", "application/zip"))
        self.assertTrue(config.agent_token, "agent token generated")
