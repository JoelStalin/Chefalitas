import logging
import threading
from datetime import timedelta

from odoo import api, fields, models

from .orca_bridge_client import post_events

_logger = logging.getLogger(__name__)

BATCH = 200
KEEP_SENT_DAYS = 7


class OrcaBridgeOutbox(models.Model):
    """Change events waiting for ORCA. Written after commit, removed from the queue only when ORCA accepts them,
    so an ORCA outage delays notifications instead of losing them. Holds ids and field names only, never values."""

    _name = "orca.bridge.outbox"
    _description = "ORCA pending change events"
    _order = "id"

    payload = fields.Json(required=True)
    state = fields.Selection([("pending", "Pending"), ("sent", "Sent")], default="pending", required=True, index=True)
    attempts = fields.Integer(default=0)
    last_error = fields.Char()
    sent_at = fields.Datetime()

    @api.model
    def _enqueue(self, events):
        return self.sudo().create([{"payload": e} for e in events])

    @api.model
    def _send_pending(self, limit=BATCH):
        """Deliver pending events in order. Rows are locked (SKIP LOCKED): the cron and the post-commit thread
        never send the same event twice."""
        settings = self.env["orca.bridge.client"]._settings()
        if not (settings["url"] and settings["connection"]):
            return 0
        self.flush_model()  # the raw query below must see states written earlier in this transaction
        self.env.cr.execute(
            "SELECT id FROM orca_bridge_outbox WHERE state = 'pending' ORDER BY id LIMIT %s FOR UPDATE SKIP LOCKED", [limit])
        rows = self.sudo().browse([r[0] for r in self.env.cr.fetchall()])
        if not rows:
            return 0
        try:
            token = self.env["orca.bridge.client"]._access_token()
        except Exception as exc:  # noqa: BLE001 - keep the events for the next attempt
            rows.write({"attempts": rows[:1].attempts + 1, "last_error": f"token: {exc}"[:250]})
            return 0
        results = post_events(settings["url"], token, [r.payload for r in rows])
        now = fields.Datetime.now()
        sent = 0
        for row, (ok, error) in zip(rows, results):
            if ok:
                row.write({"state": "sent", "sent_at": now, "last_error": False})
                sent += 1
            else:
                row.write({"attempts": row.attempts + 1, "last_error": (error or "")[:250]})
                break  # keep order: later events wait for this one
        return sent

    @api.model
    def _cron_send(self):
        while self._send_pending() == BATCH:
            self.env.cr.commit()  # long backlog: commit each batch
        self.search([("state", "=", "sent"), ("sent_at", "<", fields.Datetime.now() - timedelta(days=KEEP_SENT_DAYS))]).unlink()

    @api.model
    def _send_in_background(self):
        dbname = self.env.cr.dbname
        registry = self.env.registry

        def run():
            try:
                with registry.cursor() as cr:
                    self.with_env(self.env(cr=cr))._send_pending()
            except Exception as exc:  # noqa: BLE001 - the cron retries
                _logger.warning("orca_bridge: background send failed on %s (%s); the cron will retry", dbname, exc)

        threading.Thread(target=run, name="orca-bridge-outbox", daemon=True).start()
