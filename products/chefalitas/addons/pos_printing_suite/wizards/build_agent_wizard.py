# -*- coding: utf-8 -*-
import base64
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class BuildAgentWizard(models.TransientModel):
    _name = "build.agent.wizard"
    _description = "Upload / attach Local Printer Agent installer for device"

    device_id = fields.Many2one(
        "pos.print.device",
        string="Device",
        required=True,
        ondelete="cascade",
    )
    installer_file = fields.Binary(
        string="Installer file",
        attachment=True,
        help="Upload the LocalPrinterAgent-Setup.exe (or .zip) built for this device (token is embedded in the build).",
    )
    installer_filename = fields.Char(string="Filename")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get("active_model") == "pos.print.device" and "device_id" in (fields_list or []):
            res["device_id"] = self.env.context.get("active_id")
        return res

    def action_upload_installer(self):
        self.ensure_one()
        if not self.installer_file:
            raise UserError(_("Please select an installer file to upload."))
        IrAttachment = self.env["ir.attachment"].sudo()
        # Remove old installer for this device (same name pattern)
        old = IrAttachment.search([
            ("res_model", "=", "pos.print.device"),
            ("res_id", "=", self.device_id.id),
            ("name", "ilike", "LocalPrinterAgent-Setup%"),
        ])
        old.unlink()
        name = self.installer_filename or "LocalPrinterAgent-Setup.exe"
        if not name.lower().endswith((".exe", ".zip")):
            name = name + ".exe"
        IrAttachment.create({
            "name": name,
            "datas": self.installer_file,
            "res_model": "pos.print.device",
            "res_id": self.device_id.id,
            "type": "binary",
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": "pos.print.device",
            "view_mode": "form",
            "res_id": self.device_id.id,
            "target": "current",
        }
