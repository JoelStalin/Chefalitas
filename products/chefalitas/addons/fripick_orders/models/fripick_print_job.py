import base64
import json
import logging
import socket
import urllib.request

from odoo import fields, models

_logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 5


class FripickPrintJob(models.Model):
    """One document to print. Direct and agent printers are sent at once; gateway printers wait to be pulled."""
    _name = "fripick.print.job"
    _description = "Fripick print job"
    _order = "id"

    printer_id = fields.Many2one("fripick.printer", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="printer_id.company_id", store=True)
    kind = fields.Selection([("kitchen", "Comanda de cocina"), ("label", "Etiqueta")], required=True)
    content_type = fields.Selection([("raw", "ESC/POS"), ("pdf", "PDF")], required=True, default="raw")
    payload = fields.Text(required=True, help="Base64 of the document (ESC/POS bytes or PDF).")
    origin = fields.Char()
    state = fields.Selection([("queued", "En cola"), ("sent", "Enviado"), ("done", "Impreso"), ("failed", "Falló")],
                             default="queued", required=True, index=True)
    attempts = fields.Integer(default=0)
    error = fields.Char()

    def dispatch(self):
        for job in self.filtered(lambda j: j.state == "queued" and j.printer_id.connection != "gateway"):
            try:
                data = base64.b64decode(job.payload)
                printer = job.printer_id
                if printer.connection == "direct":
                    with socket.create_connection((printer.host, printer.port or 9100), timeout=5) as conn:
                        conn.sendall(data)
                else:
                    body = json.dumps({"type": job.content_type, "printer": printer.agent_printer_name or printer.name,
                                       "data": base64.b64encode(data).decode()}).encode()
                    req = urllib.request.Request(f"http://{printer.host}:{printer.port or 8085}/print", data=body, method="POST",
                                                 headers={"Content-Type": "application/json",
                                                          **({"Authorization": f"Bearer {printer.sudo().token}"} if printer.sudo().token else {})})
                    urllib.request.urlopen(req, timeout=10).read()
                job.write({"state": "done", "error": False})
            except Exception as exc:  # network errors stay in the job; the cron retries
                attempts = job.attempts + 1
                job.write({"attempts": attempts, "error": str(exc)[:250], "state": "failed" if attempts >= MAX_ATTEMPTS else "queued"})
                _logger.warning("Fripick print job %s failed (%s/%s): %s", job.id, attempts, MAX_ATTEMPTS, exc)

    def _cron_retry(self):
        self.search([("state", "=", "queued")], limit=200).dispatch()
