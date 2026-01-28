# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import werkzeug


class AgentDownload(http.Controller):
    @http.route(
        "/pos_printing_suite/agent/download/<int:device_id>",
        type="http",
        auth="user",
        csrf=False,
    )
    def download_agent(self, device_id, **kw):
        if not request.env.user.has_group("point_of_sale.group_pos_manager"):
            raise werkzeug.exceptions.Forbidden()
        # Minimal sudo only to read device and attachment (cross-model)
        device = request.env["pos.print.device"].sudo().browse(device_id)
        if not device.exists() or device.state == "revoked":
            raise werkzeug.exceptions.NotFound()
        attachment = (
            request.env["ir.attachment"]
            .sudo()
            .search(
                [
                    ("res_model", "=", "pos.print.device"),
                    ("res_id", "=", device.id),
                    ("name", "ilike", "LocalPrinterAgent-Setup%"),
                ],
                limit=1,
                order="id desc",
            )
        )
        if not attachment:
            raise werkzeug.exceptions.NotFound(
                "No installer built for this device yet."
            )
        content = attachment.raw
        if not content:
            raise werkzeug.exceptions.NotFound(
                "Installer file is empty."
            )
        return request.make_response(
            content,
            headers=[
                ("Content-Type", "application/octet-stream"),
                ("Content-Disposition", f"attachment; filename=\"{attachment.name}\""),
            ],
        )
