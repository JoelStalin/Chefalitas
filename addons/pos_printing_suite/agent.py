# -*- coding: utf-8 -*-
import base64
import json

from odoo import http, fields, _
from odoo.exceptions import AccessError
from odoo.http import request


class PosPrintingSuiteAgentController(http.Controller):
    def _ensure_admin(self):
        if not request.env.user.has_group("base.group_system"):
            raise AccessError(_("Only administrators can perform this action."))

    def _get_agent_token(self):
        auth = request.httprequest.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            return auth.split(" ", 1)[1].strip()
        return request.params.get("token")

    @http.route("/pos_printing_suite/agent/build", type="json", auth="user")
    def build_agent(self, config_id=None):
        self._ensure_admin()
        if not config_id:
            return {"ok": False, "error": "missing_config_id"}
        config = request.env["pos.config"].browse(int(config_id)).exists()
        if not config:
            return {"ok": False, "error": "config_not_found"}
        attachment = config._build_agent_installer()
        return {
            "ok": True,
            "name": attachment.name,
            "download_url": config.agent_download_url,
        }

    @http.route("/pos_printing_suite/agent/download", type="http", auth="user")
    def download_agent(self, config_id=None, **kwargs):
        self._ensure_admin()
        if not config_id:
            return request.not_found()
        config = request.env["pos.config"].browse(int(config_id)).exists()
        if not config:
            return request.not_found()
        if not config.agent_artifact_id:
            config._build_agent_installer()
        attachment = config.agent_artifact_id
        data = base64.b64decode(attachment.datas or b"")
        headers = [
            ("Content-Type", "application/zip"),
            ("Content-Disposition", f'attachment; filename="{attachment.name}"'),
        ]
        return request.make_response(data, headers)

    @http.route("/pos_printing_suite/agent/policy.ps1", type="http", auth="user")
    def download_loopback_policy(self, config_id=None, **kwargs):
        self._ensure_admin()
        if not config_id:
            return request.not_found()
        config = request.env["pos.config"].browse(int(config_id)).exists()
        if not config:
            return request.not_found()
        base_url = request.env["ir.config_parameter"].sudo().get_param("web.base.url") or ""
        if not base_url:
            base_url = request.httprequest.host_url.rstrip("/")
        base_url = base_url.rstrip("/")
        urls = {base_url} if base_url else set()
        if base_url.startswith("http://"):
            urls.add("https://" + base_url[len("http://"):])
        elif base_url.startswith("https://"):
            urls.add("http://" + base_url[len("https://"):])
        url_list = ", ".join([f"'{u}'" for u in sorted(urls)])
        script = (
            "$ErrorActionPreference = 'Stop'\n"
            "$chromePath = 'HKLM:\\\\SOFTWARE\\\\Policies\\\\Google\\\\Chrome'\n"
            "New-Item -Path $chromePath -Force | Out-Null\n"
            "New-ItemProperty -Path $chromePath -Name InsecurePrivateNetworkRequestsAllowed -PropertyType DWord -Value 1 -Force | Out-Null\n"
            f"New-ItemProperty -Path $chromePath -Name InsecurePrivateNetworkRequestsAllowedForUrls -PropertyType MultiString -Value @({url_list}) -Force | Out-Null\n"
            "$edgePath = 'HKLM:\\\\SOFTWARE\\\\Policies\\\\Microsoft\\\\Edge'\n"
            "New-Item -Path $edgePath -Force | Out-Null\n"
            "New-ItemProperty -Path $edgePath -Name InsecurePrivateNetworkRequestsAllowed -PropertyType DWord -Value 1 -Force | Out-Null\n"
            f"New-ItemProperty -Path $edgePath -Name InsecurePrivateNetworkRequestsAllowedForUrls -PropertyType MultiString -Value @({url_list}) -Force | Out-Null\n"
            "Write-Host 'Loopback policy applied. Restart Chrome/Edge.'\n"
        )
        headers = [
            ("Content-Type", "application/octet-stream"),
            ("Content-Disposition", 'attachment; filename="enable_loopback_policy.ps1"'),
        ]
        return request.make_response(script, headers)

    @http.route("/pos_printing_suite/agent/ping", type="json", auth="public", csrf=False)
    def agent_ping(self, token=None, version=None, status=None, pos_config_id=None, printers=None, **kwargs):
        token = token or self._get_agent_token()
        if not token:
            return {"ok": False, "error": "missing_token"}
        config = request.env["pos.config"].sudo().search([("agent_token", "=", token)], limit=1)
        if not config:
            return {"ok": False, "error": "invalid_token"}
        config.sudo().write({
            "agent_last_seen": fields.Datetime.now(),
            "agent_version": version or config.agent_version,
            "agent_enabled": True,
        })
        if printers:
            if isinstance(printers, str):
                try:
                    printers = json.loads(printers)
                except Exception:
                    printers = []
            self._sync_agent_printers(config, printers)
        return {"ok": True}

    def _sync_agent_printers(self, config, printers):
        if not isinstance(printers, (list, tuple)):
            return
        names = [p for p in printers if isinstance(p, str) and p.strip()]
        if not names:
            return
        Printer = request.env["pos.printing.agent.printer"].sudo()
        existing = Printer.search([("pos_config_id", "=", config.id)])
        existing_names = set(existing.mapped("name"))
        now = fields.Datetime.now()
        for name in names:
            if name in existing_names:
                existing.filtered(lambda r: r.name == name).write({"last_seen": now})
            else:
                Printer.create({
                    "name": name,
                    "pos_config_id": config.id,
                    "last_seen": now,
                })
        # Remove printers no longer reported
        to_remove = existing.filtered(lambda r: r.name not in set(names))
        if to_remove:
            to_remove.unlink()

    @http.route("/pos_printing_suite/agent/config", type="json", auth="public", csrf=False)
    def agent_config(self, token=None, **kwargs):
        token = token or self._get_agent_token()
        if not token:
            return {"ok": False, "error": "missing_token"}
        config = request.env["pos.config"].sudo().search([("agent_token", "=", token)], limit=1)
        if not config:
            return {"ok": False, "error": "invalid_token"}
        return {
            "ok": True,
            "server_url": request.env["ir.config_parameter"].sudo().get_param("web.base.url"),
            "pos_config_id": config.id,
            "printing_mode": config.printing_mode,
            "local_agent_host": config.local_agent_host,
            "local_agent_port": config.local_agent_port,
            "any_printer_ip": config.any_printer_ip,
            "any_printer_port": config.any_printer_port,
            "local_printer_cashier_name": config.local_printer_cashier_name,
            "local_printer_kitchen_name": config.local_printer_kitchen_name,
        }
