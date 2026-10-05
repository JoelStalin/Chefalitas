# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import secrets


class PosPrintDevice(models.Model):
    _name = "pos.print.device"
    _description = "POS Print Device (Local Agent binding)"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True, tracking=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    pos_config_id = fields.Many2one(
        "pos.config",
        string="POS Config",
        ondelete="cascade",
        required=True,
    )
    token = fields.Char(readonly=True, copy=False, index=True)
    agent_version = fields.Char(readonly=True)
    last_seen = fields.Datetime(readonly=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("revoked", "Revoked"),
        ],
        default="draft",
        tracking=True,
    )

    _sql_constraints = [
        ("token_uniq", "unique(token)", "Token must be unique."),
    ]

    def _generate_token(self):
        return secrets.token_urlsafe(32)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("token"):
                vals["token"] = self._generate_token()
        return super().create(vals_list)

    def action_activate(self):
        self.write({"state": "active"})

    def action_revoke(self):
        self.write({"state": "revoked"})

    def action_rotate_token(self):
        for rec in self:
            rec.write({"token": rec._generate_token()})

    @api.constrains("company_id", "pos_config_id")
    def _check_company_config(self):
        for rec in self:
            if rec.pos_config_id and rec.company_id and rec.pos_config_id.company_id != rec.company_id:
                raise ValidationError(
                    _("The POS Config company must match the device company.")
                )

    def action_upload_installer_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Upload Agent Installer",
            "res_model": "build.agent.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_device_id": self.id},
        }
