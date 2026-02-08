# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class PosPrintingSuiteAgentInstallWizard(models.TransientModel):
    _name = "pos.printing.suite.agent.install.wizard"
    _description = "POS Printing Suite Agent Install Wizard"

    pos_config_id = fields.Many2one("pos.config", required=True)
    download_url = fields.Char(compute="_compute_download_url")
    instructions = fields.Html(compute="_compute_instructions", sanitize=False)

    @api.depends("pos_config_id")
    def _compute_download_url(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        for rec in self:
            if not base_url or not rec.pos_config_id:
                rec.download_url = False
            else:
                rec.download_url = (
                    f"{base_url}/pos_printing_suite/agent/download?config_id={rec.pos_config_id.id}"
                )

    @api.depends("download_url")
    def _compute_instructions(self):
        for rec in self:
            if not rec.download_url:
                rec.instructions = _("<p>No download URL available.</p>")
                continue
            rec.instructions = _(
                """
                <ol>
                  <li>Download the installer ZIP.</li>
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
