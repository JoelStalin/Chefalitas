# -*- coding: utf-8 -*-
import base64
import io
import json
import re
import secrets
import zipfile

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError, UserError


class PosConfig(models.Model):
    _inherit = "pos.config"

    AGENT_ARTIFACT_VERSION = "0.1.0"

    printing_mode = fields.Selection(
        [
            ("odoo_default", "Odoo (Standard)"),
            ("local_agent", "Local Agent (Windows)"),
            ("hw_proxy", "HW Proxy / Any Printer"),
        ],
        default="odoo_default",
        required=True,
    )
    local_agent_host = fields.Char(
        string="Local Agent IP",
        default="127.0.0.1",
    )
    local_agent_port = fields.Integer(
        string="Local Agent Port",
        default=9060,
    )
    local_printer_cashier_name = fields.Char(string="Printer (Cashier)")
    local_printer_kitchen_name = fields.Char(string="Printer (Kitchen)")
    any_printer_ip = fields.Char(
        string="HW Proxy Host",
        help="Host/IP for HW Proxy when printing_mode is HW Proxy.",
        default="127.0.0.1",
    )
    any_printer_port = fields.Integer(
        string="HW Proxy Port",
        default=8069,
    )
    printing_suite_allowed = fields.Boolean(
        compute="_compute_printing_suite_allowed",
        help="True when the user is allowed to use the Printing Suite and mode is enabled.",
    )

    agent_enabled = fields.Boolean(string="Windows Agent Enabled", default=False)
    agent_token = fields.Char(
        string="Agent Token",
        copy=False,
        groups="base.group_system",
    )
    agent_last_seen = fields.Datetime(string="Agent Last Seen", readonly=True)
    agent_version = fields.Char(string="Agent Version", readonly=True)
    agent_status = fields.Selection(
        [
            ("unknown", "Unknown"),
            ("online", "Online"),
            ("offline", "Offline"),
        ],
        compute="_compute_agent_status",
        string="Agent Status",
    )
    agent_artifact_id = fields.Many2one(
        "ir.attachment",
        string="Agent Installer",
        readonly=True,
        copy=False,
        groups="base.group_system",
    )
    agent_download_url = fields.Char(
        compute="_compute_agent_download_url",
        string="Agent Download URL",
        groups="base.group_system",
    )

    @api.depends("printing_mode")
    @api.depends_context("uid")
    def _compute_printing_suite_allowed(self):
        for rec in self:
            rec.printing_suite_allowed = rec._is_printing_suite_allowed()

    def _is_printing_suite_allowed(self):
        self.ensure_one()
        if self.printing_mode not in ("local_agent", "hw_proxy"):
            return False
        group = self.env.ref("pos_printing_suite.group_pos_printing_suite_printing", raise_if_not_found=False)
        if not group:
            return False
        return group in self.env.user.groups_id

    @api.depends("agent_last_seen")
    def _compute_agent_status(self):
        threshold_minutes = 5
        now = fields.Datetime.now()
        for rec in self:
            if not rec.agent_last_seen:
                rec.agent_status = "unknown"
                continue
            delta = now - rec.agent_last_seen
            rec.agent_status = "online" if delta.total_seconds() <= threshold_minutes * 60 else "offline"

    def _compute_agent_download_url(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        for rec in self:
            if not base_url:
                rec.agent_download_url = False
            else:
                rec.agent_download_url = (
                    f"{base_url}/pos_printing_suite/agent/download?config_id={rec.id}"
                )

    def _generate_agent_token(self):
        return secrets.token_urlsafe(32)

    def _ensure_agent_token(self):
        for rec in self:
            if not rec.agent_token:
                rec.agent_token = rec._generate_agent_token()

    def action_regenerate_agent_token(self):
        self._ensure_admin()
        for rec in self:
            rec.agent_token = rec._generate_agent_token()
        return self._notify(_("Agent token regenerated."), "success")

    def action_build_agent_installer(self):
        self._ensure_admin()
        attachment = self._build_agent_installer()
        return self._notify(
            _("Installer generated: %s") % attachment.name, "success"
        )

    def action_download_agent_installer(self):
        self._ensure_admin()
        self.ensure_one()
        if not self.agent_artifact_id:
            self._build_agent_installer()
        if not self.agent_download_url:
            raise UserError(_("Download URL is not available."))
        return {
            "type": "ir.actions.act_url",
            "url": self.agent_download_url,
            "target": "self",
        }

    def action_open_agent_install_wizard(self):
        self._ensure_admin()
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Install Windows Agent"),
            "res_model": "pos.printing.suite.agent.install.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_pos_config_id": self.id},
        }

    def _build_agent_installer(self):
        self.ensure_one()
        self._ensure_agent_token()
        artifact_name = f"windows_agent_v{self.AGENT_ARTIFACT_VERSION}.zip"
        payload = self._build_agent_zip_payload()
        attachment = self.env["ir.attachment"].create({
            "name": artifact_name,
            "type": "binary",
            "datas": base64.b64encode(payload),
            "res_model": "pos.config",
            "res_id": self.id,
            "mimetype": "application/zip",
        })
        self.agent_artifact_id = attachment
        return attachment

    def _build_agent_zip_payload(self):
        self.ensure_one()
        config = {
            "server_url": self.env["ir.config_parameter"].sudo().get_param("web.base.url"),
            "token": self.agent_token,
            "pos_config_id": self.id,
        }
        installer_ps1 = (
            r"$ErrorActionPreference = 'Stop'" + "\n"
            r"$baseDir = Join-Path $env:ProgramData 'PosPrintingSuite\Agent'" + "\n"
            r"New-Item -ItemType Directory -Force -Path $baseDir | Out-Null" + "\n"
            r"Copy-Item -Path (Join-Path $PSScriptRoot '*') -Destination $baseDir -Recurse -Force" + "\n"
            r"$exe = Join-Path $baseDir 'agent.exe'" + "\n"
            r"sc.exe create PosPrintingSuiteAgent binPath= `"$exe`" start= auto | Out-Null" + "\n"
            r"sc.exe start PosPrintingSuiteAgent | Out-Null" + "\n"
            r"Write-Host 'Agent installed and started.'" + "\n"
        )
        uninstall_ps1 = (
            r"$ErrorActionPreference = 'SilentlyContinue'" + "\n"
            r"sc.exe stop PosPrintingSuiteAgent | Out-Null" + "\n"
            r"sc.exe delete PosPrintingSuiteAgent | Out-Null" + "\n"
            r"$baseDir = Join-Path $env:ProgramData 'PosPrintingSuite\Agent'" + "\n"
            r"Remove-Item -Recurse -Force $baseDir" + "\n"
            r"Write-Host 'Agent uninstalled.'" + "\n"
        )
        readme_txt = (
            "Windows Agent (placeholder)\n"
            "1) Run install.ps1 as Administrator.\n"
            "2) The service will start automatically.\n"
            "3) Replace agent.exe with a real build (PyInstaller/.NET) later.\n"
        )
        agent_placeholder = (
            "PLACEHOLDER EXECUTABLE\n"
            "Build a real Windows service binary and replace this file.\n"
        )

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
            zipf.writestr("config.json", json.dumps(config, indent=2))
            zipf.writestr("install.ps1", installer_ps1)
            zipf.writestr("uninstall.ps1", uninstall_ps1)
            zipf.writestr("README.txt", readme_txt)
            zipf.writestr("agent.exe", agent_placeholder)
        return buffer.getvalue()

    def _notify(self, message, notif_type="info"):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("POS Printing Suite"),
                "message": message,
                "type": notif_type,
                "sticky": False,
            },
        }

    def _ensure_admin(self):
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Only administrators can perform this action."))

    def _normalize_port_value(self, value, field_label):
        if value in (None, False, ""):
            return None
        if isinstance(value, str):
            cleaned = re.sub(r"[,\s]", "", value)
        else:
            cleaned = str(value)
        try:
            port = int(cleaned)
        except (TypeError, ValueError):
            raise ValidationError(_("%s must be an integer between 1 and 65535.") % field_label)
        if port < 1 or port > 65535:
            raise ValidationError(_("%s must be between 1 and 65535.") % field_label)
        return port

    def _normalize_host_value(self, value, field_label):
        if not value:
            return None
        host = value.strip()
        if not host or re.search(r"[\s,]", host):
            raise ValidationError(_("%s is invalid.") % field_label)
        return host

    @api.constrains("any_printer_ip", "any_printer_port")
    def _check_hw_proxy_settings(self):
        for rec in self:
            if rec.printing_mode != "hw_proxy":
                continue
            rec._normalize_host_value(rec.any_printer_ip, _("HW Proxy Host"))
            rec._normalize_port_value(rec.any_printer_port, _("HW Proxy Port"))

    @api.onchange("any_printer_port")
    def _onchange_any_printer_port(self):
        if isinstance(self.any_printer_port, str):
            self.any_printer_port = self._normalize_port_value(
                self.any_printer_port, _("HW Proxy Port")
            )

    @api.onchange("local_agent_port")
    def _onchange_local_agent_port(self):
        if isinstance(self.local_agent_port, str):
            self.local_agent_port = self._normalize_port_value(
                self.local_agent_port, _("Local Agent Port")
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "any_printer_port" in vals:
                vals["any_printer_port"] = self._normalize_port_value(
                    vals.get("any_printer_port"), _("HW Proxy Port")
                )
            if "local_agent_port" in vals:
                vals["local_agent_port"] = self._normalize_port_value(
                    vals.get("local_agent_port"), _("Local Agent Port")
                )
            if "any_printer_ip" in vals:
                vals["any_printer_ip"] = self._normalize_host_value(
                    vals.get("any_printer_ip"), _("HW Proxy Host")
                )
        records = super().create(vals_list)
        records._ensure_agent_token()
        return records

    def write(self, vals):
        if "any_printer_port" in vals:
            vals["any_printer_port"] = self._normalize_port_value(
                vals.get("any_printer_port"), _("HW Proxy Port")
            )
        if "local_agent_port" in vals:
            vals["local_agent_port"] = self._normalize_port_value(
                vals.get("local_agent_port"), _("Local Agent Port")
            )
        if "any_printer_ip" in vals:
            vals["any_printer_ip"] = self._normalize_host_value(
                vals.get("any_printer_ip"), _("HW Proxy Host")
            )
        res = super().write(vals)
        if "agent_token" in vals:
            return res
        self._ensure_agent_token()
        return res

    def _normalize_existing_hw_proxy_ports(self):
        for rec in self.sudo().search([]):
            updates = {}
            if rec.any_printer_port:
                updates["any_printer_port"] = rec._normalize_port_value(
                    rec.any_printer_port, _("HW Proxy Port")
                )
            if rec.local_agent_port:
                updates["local_agent_port"] = rec._normalize_port_value(
                    rec.local_agent_port, _("Local Agent Port")
                )
            if updates:
                rec.write(updates)

    def _loader_params_pos_config(self):
        parent = getattr(super(), "_loader_params_pos_config", None)
        params = parent() if callable(parent) else {"fields": []}
        params["fields"].extend([
            "printing_mode",
            "printing_suite_allowed",
            "local_agent_host",
            "local_agent_port",
            "local_printer_cashier_name",
            "local_printer_kitchen_name",
            "any_printer_ip",
            "any_printer_port",
        ])
        return params

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields = super()._load_pos_data_fields(config_id)
        # If fields is falsy, the base loader will load all fields; keep that behavior.
        if not fields:
            return fields
        extras = [
            "printing_mode",
            "printing_suite_allowed",
            "local_agent_host",
            "local_agent_port",
            "local_printer_cashier_name",
            "local_printer_kitchen_name",
            "any_printer_ip",
            "any_printer_port",
        ]
        for f in extras:
            if f not in fields:
                fields.append(f)
        return fields

    # NOTE: no device/token required; printing suite is configured by printer names only.
