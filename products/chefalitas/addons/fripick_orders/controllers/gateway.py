import io
import os
import zipfile

from odoo import http
from odoo.http import request

GATEWAY_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gateway")


class FripickGateway(http.Controller):
    """Pull API for the local gateway (Odoo in the cloud): the gateway authenticates with its printer token, takes the
    queued jobs and acknowledges each one. No inbound port is opened at the restaurant."""

    def _printer(self):
        auth = request.httprequest.headers.get("Authorization", "")
        token = auth[7:] if auth.startswith("Bearer ") else ""
        if len(token) < 20:
            return request.env["fripick.printer"].browse()
        return request.env["fripick.printer"].sudo().search([("token", "=", token), ("connection", "=", "gateway")], limit=1)

    # readonly=False: Odoo 20 runs GET routes read-only, and taking the jobs marks them as sent
    @http.route("/fripick/gateway/jobs", type="http", auth="none", methods=["GET"], csrf=False, readonly=False)
    def jobs(self):
        printer = self._printer()
        if not printer:
            return request.make_json_response({"error": "unauthorized"}, status=401)
        jobs = request.env["fripick.print.job"].sudo().search([("printer_id", "=", printer.id), ("state", "=", "queued")], limit=20)
        jobs.write({"state": "sent"})
        payload = [{"id": job.id, "type": job.content_type,
                    "data": job.payload} for job in jobs]
        return request.make_json_response({"printer": {"host": printer.host, "port": printer.port, "paper": printer.paper},
                                           "jobs": payload})

    @http.route("/fripick/gateway/ack", type="http", auth="none", methods=["POST"], csrf=False, readonly=False)
    def ack(self):
        printer = self._printer()
        if not printer:
            return request.make_json_response({"error": "unauthorized"}, status=401)
        body = request.get_json_data() or {}
        job = request.env["fripick.print.job"].sudo().search(
            [("id", "=", int(body.get("id") or 0)), ("printer_id", "=", printer.id)], limit=1)
        if job:
            ok = bool(body.get("ok"))
            job.write({"state": "done" if ok else "queued", "error": False if ok else str(body.get("error") or "")[:250],
                       "attempts": job.attempts + (0 if ok else 1)})
        return request.make_json_response({"ok": bool(job)})

    @http.route("/fripick/gateway/download", type="http", auth="user")
    def download(self):
        """Zip with the gateway and its installers (Windows service, macOS launchd, Android with Termux)."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for name in sorted(os.listdir(GATEWAY_DIR)):
                zf.write(os.path.join(GATEWAY_DIR, name), f"fripick-gateway/{name}")
        return request.make_response(buf.getvalue(), headers=[
            ("Content-Type", "application/zip"),
            ("Content-Disposition", 'attachment; filename="fripick-gateway.zip"'),
        ])
