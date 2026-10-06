import logging
import threading

import requests

from odoo import api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

EVENTS_KEY = "orca_bridge.events"
TIMEOUT = 5
MAX_IDS = 200


def post_events(url, token, events):
    """Send change events to ORCA. Runs after commit in a background thread: never raises."""
    for event in events:
        try:
            response = requests.post(
                f"{url}/api/orca/odoo-bridge/events",
                json=event,
                headers={"Authorization": f"Bearer {token}"},
                timeout=TIMEOUT,
            )
        except requests.RequestException as exc:
            _logger.warning("orca_bridge: ORCA not reachable (%s); event %s/%s dropped",
                            exc, event["model"], event["event"])
            continue
        if response.status_code >= 300:
            _logger.warning("orca_bridge: ORCA refused event %s/%s: HTTP %s",
                            event["model"], event["event"], response.status_code)


class OrcaBridgeClient(models.AbstractModel):
    """Odoo -> ORCA: settings, requests and change events."""

    _name = "orca.bridge.client"
    _description = "ORCA bridge client"

    @api.model
    def _settings(self):
        params = self.env["ir.config_parameter"].sudo()
        return {
            "url": (params.get_str("orca_bridge.url") or "").rstrip("/"),
            "token": params.get_str("orca_bridge.token") or "",
            "connection": params.get_str("orca_bridge.connection_id") or self.env.cr.dbname,
            "push_events": params.get_bool("orca_bridge.push_events"),
        }

    @api.model
    def _request(self, method, path, payload=None):
        settings = self._settings()
        if not settings["url"] or not settings["token"]:
            raise UserError(self.env._("Configure la URL y el token de ORCA en Ajustes > ORCA."))
        try:
            response = requests.request(
                method, settings["url"] + path, json=payload, timeout=TIMEOUT,
                headers={"Authorization": f"Bearer {settings['token']}"},
            )
        except requests.RequestException as exc:
            raise UserError(self.env._("ORCA no responde: %s", exc)) from exc
        try:
            body = response.json()
        except ValueError:
            body = {}
        if response.status_code >= 300:
            error = (body or {}).get("error") or {}
            raise UserError(self.env._(
                "ORCA respondio %(status)s: %(message)s",
                status=response.status_code, message=error.get("message") or response.text[:200],
            ))
        return body

    @api.model
    def _push_event(self, records, event, fields=()):
        """Queue a change notification; it is sent only if the transaction commits."""
        if not records.ids:
            return
        settings = self._settings()
        if not (settings["push_events"] and settings["url"] and settings["token"]):
            return
        postcommit = self.env.cr.postcommit
        pending = postcommit.data.get(EVENTS_KEY)
        if pending is None:
            pending = postcommit.data[EVENTS_KEY] = {}
            postcommit.add(self._flush_callback(settings, pending))
        entry = pending.setdefault((records._name, event), {"ids": set(), "fields": set()})
        entry["ids"].update(records.ids)
        entry["fields"].update(fields)

    @api.model
    def _events_payload(self, connection, pending):
        events = []
        for (model, event), entry in sorted(pending.items()):
            ids = sorted(entry["ids"])
            for start in range(0, len(ids), MAX_IDS):
                events.append({
                    "connection": connection,
                    "model": model,
                    "event": event,
                    "ids": ids[start:start + MAX_IDS],
                    "fields": sorted(entry["fields"])[:200],
                })
        return events

    @api.model
    def _flush_callback(self, settings, pending):
        def flush():
            events = self._events_payload(settings["connection"], pending)
            if events:
                threading.Thread(
                    target=post_events, args=(settings["url"], settings["token"], events),
                    name="orca-bridge-events", daemon=True,
                ).start()
        return flush
