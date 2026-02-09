# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class PosPrintingSuiteAgentInstallWizard(models.TransientModel):
    _name = "pos.printing.suite.agent.install.wizard"
    _description = "POS Printing Suite Agent Install Wizard"

    pos_config_id = fields.Many2one("pos.config", required=True)
    download_url = fields.Char(compute="_compute_download_url")
    instructions = fields.Html(compute="_compute_instructions", sanitize=False)
    installer_name = fields.Char(compute="_compute_installer_info")
    is_msi = fields.Boolean(compute="_compute_installer_info")

    @api.depends("pos_config_id")
    def _compute_download_url(self):
        for rec in self:
            if not rec.pos_config_id:
                rec.download_url = False
            else:
                rec.download_url = (
                    f"/pos_printing_suite/agent/download?config_id={rec.pos_config_id.id}"
                )

    @api.depends("pos_config_id", "pos_config_id.agent_artifact_id", "pos_config_id.agent_artifact_id.name", "pos_config_id.agent_artifact_id.mimetype")
    def _compute_installer_info(self):
        for rec in self:
            name = False
            is_msi = False
            if rec.pos_config_id and rec.pos_config_id.agent_artifact_id:
                attachment = rec.pos_config_id.agent_artifact_id
                name = attachment.name
                is_msi = bool(name and name.lower().endswith(".msi")) or (attachment.mimetype == "application/x-msi")
            rec.installer_name = name
            rec.is_msi = is_msi

    @api.depends("download_url", "is_msi")
    def _compute_instructions(self):
        for rec in self:
            if not rec.download_url:
                rec.instructions = _("<p>No download URL available.</p>")
                continue
            if rec.is_msi:
                rec.instructions = _(
                    """
                    <ol>
                      <li>Download the <strong>MSI</strong> installer.</li>
                      <li>Run it as Administrator and finish the wizard.</li>
                      <li>The service, tray icon and shortcuts are installed automatically.</li>
                      <li>If your POS runs on HTTPS, the loopback policy is applied automatically.</li>
                    </ol>
                    """
                )
            else:
                rec.instructions = _(
                    """
                    <ol>
                      <li>Download the installer <strong>ZIP</strong>.</li>
                      <li>Extract it on the Windows POS machine.</li>
                      <li>Right-click <code>install.ps1</code> and run as Administrator.</li>
                      <li>If your POS runs on HTTPS, run <code>enable_loopback_policy.ps1</code> as Administrator.</li>
                      <li>The service will start automatically and report status back to Odoo.</li>
                    </ol>
                    """
                )

    def action_download(self):
        self.ensure_one()
        if not self.download_url:
            return {"type": "ir.actions.act_window_close"}
        return {
            "type": "ir.actions.act_url",
            "url": self.download_url,
            "target": "self",
        }
