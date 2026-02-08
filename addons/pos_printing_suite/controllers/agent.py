# -*- coding: utf-8 -*-
import base64

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

    @http.route("/pos_printing_suite/agent/ping", type="json", auth="public", csrf=False)
    def agent_ping(self, token=None, version=None, status=None, pos_config_id=None, **kwargs):
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
        return {"ok": True}

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
