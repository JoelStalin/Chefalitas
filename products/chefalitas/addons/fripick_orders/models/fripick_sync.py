import json
import logging
import urllib.request

from odoo import api, fields, models

from .compat import param_str

_logger = logging.getLogger(__name__)


class FripickSync(models.AbstractModel):
    """Daily sync of the Fripick companies. Source: a JSON feed (system parameters fripick.sync_url and
    fripick.sync_token). Fripick has no official API, so the feed is produced by the ORCA scraper and published for
    Odoo; Odoo never scrapes. Each item: {"external_id", "name", "vat", "invoice_issuer": "fripick" | "company"}."""
    _name = "fripick.sync"
    _description = "Fripick daily sync"

    @api.model
    def _fetch(self):
        url = param_str(self.env, "fripick.sync_url")
        if not url:
            _logger.info("Fripick sync skipped: fripick.sync_url is not set")
            return []
        token = param_str(self.env, "fripick.sync_token")
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    @api.model
    def apply(self, items):
        """Updates companies that already exist (matched by Fripick ID, then by RNC). Unknown companies are only
        logged: creating a company has accounting consequences and stays a human decision."""
        Company = self.env["res.company"].sudo()
        updated, unknown = 0, []
        for item in items or []:
            ext, vat = str(item.get("external_id") or ""), str(item.get("vat") or "")
            company = Company.browse()
            if ext:
                company = Company.search([("fripick_external_id", "=", ext)], limit=1)
            if not company and vat:
                company = Company.search([("vat", "=", vat)], limit=1)
            if not company:
                unknown.append(ext or vat or str(item.get("name")))
                continue
            vals = {"fripick_external_id": ext or company.fripick_external_id, "fripick_last_sync": fields.Datetime.now()}
            if item.get("invoice_issuer") in ("fripick", "company"):
                vals["fripick_invoice_issuer"] = item["invoice_issuer"]
            company.write(vals)
            updated += 1
        if unknown:
            _logger.warning("Fripick sync: %s companies not in Odoo: %s", len(unknown), ", ".join(unknown[:20]))
        return {"updated": updated, "unknown": unknown}

    @api.model
    def _cron_daily_sync(self):
        try:
            return self.apply(self._fetch())
        except Exception as exc:  # logged; the next daily run retries
            _logger.error("Fripick daily sync failed: %s", exc)
            return {"updated": 0, "unknown": [], "error": str(exc)}
