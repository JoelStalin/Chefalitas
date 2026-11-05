import hashlib
import os

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AiProviderJob(models.Model):
    _name = "orca.ai.provider.job"
    _description = "ORCA generic AI provider job"
    _order = "priority desc, create_date"

    name = fields.Char(required=True)
    provider = fields.Char(required=True, index=True)
    model = fields.Char(required=True)
    idempotency_key = fields.Char(required=True, copy=False, index=True)
    prompt = fields.Text(required=True)
    state = fields.Selection(
        [("queued", "Queued"), ("processing", "Processing"), ("done", "Done"), ("failed", "Failed")],
        default="queued", required=True, index=True,
    )
    response = fields.Text(readonly=True)
    error = fields.Text(readonly=True)
    attempts = fields.Integer(default=0, readonly=True)
    priority = fields.Integer(default=10)

    _idempotency_key_unique = models.Constraint(
        "UNIQUE(idempotency_key)",
        "Idempotency key must be unique.",
    )

    @api.model
    def enqueue(self, provider, model, prompt, idempotency_key=None, name=None):
        if not provider or not model or not prompt or not prompt.strip():
            raise ValidationError("Provider, model and prompt are required.")
        key = idempotency_key or hashlib.sha256(f"{provider}:{model}:{prompt}".encode()).hexdigest()
        existing = self.search([("idempotency_key", "=", key)], limit=1)
        return existing or self.create({"name": name or f"{provider} job", "provider": provider, "model": model, "prompt": prompt, "idempotency_key": key})

    @api.model
    def _cron_process_queue(self, limit=10):
        for job in self.search([("state", "=", "queued")], limit=limit, order="priority desc, create_date"):
            job._process_one()
        return True

    def _process_one(self):
        self.ensure_one()
        self.write({"state": "processing", "attempts": self.attempts + 1})
        if not os.getenv(f"{self.provider.upper()}_API_KEY"):
            self.write({"state": "failed", "error": f"{self.provider.upper()}_API_KEY is not configured."})
            return False
        self.write({"state": "done", "response": "queued provider response pending adapter"})
        return True
