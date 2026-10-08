"""One conversation per WhatsApp number and account; messages in and out with their attachments.

Works on its own (Discuss-like chatter, reply button). Other modules react to inbound messages by overriding
`_on_inbound(message)`; ORCA reads/drives the same models through Odoo's JSON-2 API and, when the orca_bridge
module is installed, is notified of new messages (optional, detected at runtime: no hard dependency)."""
import base64
import logging

from markupsafe import Markup, escape

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class GsWhatsappConversation(models.Model):
    _name = "gs.whatsapp.conversation"
    _description = "WhatsApp conversation"
    _inherit = ["mail.thread"]
    _order = "last_message_at desc, id desc"
    _rec_name = "display_label"

    account_id = fields.Many2one("gs.whatsapp.account", required=True, ondelete="cascade")
    wa_number = fields.Char("WhatsApp number", required=True, index=True,
                            help="International format, digits only (for a group: the group id)")
    is_group = fields.Boolean("Group", help="WhatsApp group: each message keeps its own sender")
    name = fields.Char("Group name")
    partner_id = fields.Many2one("res.partner")
    message_ids_wa = fields.One2many("gs.whatsapp.message", "conversation_id", string="WhatsApp messages")
    last_message_at = fields.Datetime(index=True)
    last_inbound_at = fields.Datetime(help="Free-form replies are allowed for 24 h after the customer's last message")
    display_label = fields.Char(compute="_compute_display_label")

    _number_unique = models.Constraint("UNIQUE(account_id, wa_number)", "One conversation per number and account.")

    @api.depends("partner_id", "wa_number")
    def _compute_display_label(self):
        for conv in self:
            if conv.is_group:
                conv.display_label = f"{conv.name or 'Grupo'} (grupo)"
            else:
                conv.display_label = f"{conv.partner_id.name} (+{conv.wa_number})" if conv.partner_id else f"+{conv.wa_number}"

    @api.model
    def _partner_for_number(self, number, profile_name=None):
        number = "".join(ch for ch in number if ch.isdigit())
        partner = self.env["res.partner"].search(
            ["|", ("phone_sanitized", "=", f"+{number}"), ("phone", "=", f"+{number}")], limit=1)
        return partner or self.env["res.partner"].create({"name": profile_name or f"+{number}", "phone": f"+{number}"})

    @api.model
    def _for_group(self, account, group_id, name=None):
        group_id = "".join(ch for ch in group_id.split("@")[0] if ch.isdigit() or ch == "-")
        conv = self.search([("account_id", "=", account.id), ("wa_number", "=", group_id), ("is_group", "=", True)], limit=1)
        return conv or self.create({"account_id": account.id, "wa_number": group_id, "is_group": True, "name": name})

    @api.model
    def _for_number(self, account, number, profile_name=None):
        number = "".join(ch for ch in number if ch.isdigit())
        conv = self.search([("account_id", "=", account.id), ("wa_number", "=", number)], limit=1)
        if conv:
            return conv
        partner = self.env["res.partner"].search(
            ["|", ("phone_sanitized", "=", f"+{number}"), ("phone", "=", f"+{number}")], limit=1)
        if not partner:
            partner = self.env["res.partner"].create({"name": profile_name or f"+{number}", "phone": f"+{number}"})
        return self.create({"account_id": account.id, "wa_number": number, "partner_id": partner.id})

    # ------------------------------------------------------------------ inbound
    def _receive(self, wa_id, kind, text="", media=None, author=None):
        """Store an inbound message (media = (filename, bytes, mimetype)) and run the inbound hook.
        author: the sender (in a group, each message has its own); defaults to the conversation contact."""
        self.ensure_one()
        author = author or self.partner_id
        attachment = self.env["ir.attachment"]
        if media:
            name, data, mimetype = media
            attachment = attachment.create({"name": name, "raw": data, "mimetype": mimetype,
                                            "res_model": self._name, "res_id": self.id})
        message = self.env["gs.whatsapp.message"].create({
            "conversation_id": self.id, "direction": "in", "wa_message_id": wa_id, "kind": kind,
            "body": text or "", "attachment_id": attachment.id or False, "author_id": author.id})
        now = fields.Datetime.now()
        self.write({"last_message_at": now, "last_inbound_at": now})
        self.message_post(body=Markup("<b>WhatsApp:</b> ") + escape(text or _("(%s)", kind)),
                          author_id=author.id, attachment_ids=attachment.ids, message_type="comment",
                          subtype_xmlid="mail.mt_note")
        self._notify_orca(message)
        self._on_inbound(message)
        return message

    def _on_inbound(self, message):
        """Extension point: modules override it to react to inbound messages (e.g. purchase invoices)."""
        return False

    def _notify_orca(self, message):
        client = self.env.get("orca.bridge.client")
        if client is not None and hasattr(client, "_push_event"):
            client._push_event(message, "whatsapp_inbound", ["kind", "body", "attachment_id"])

    # ------------------------------------------------------------------ outbound
    def send_text(self, text):
        """Reply in the conversation. Public: ORCA calls it through the JSON-2 API."""
        self.ensure_one()
        to = f"{self.wa_number}@g.us" if self.is_group else self.wa_number
        wa_id = self.account_id._send_text(to, text)
        message = self.env["gs.whatsapp.message"].create({
            "conversation_id": self.id, "direction": "out", "wa_message_id": wa_id, "kind": "text", "body": text,
            "author_id": self.env.user.partner_id.id})
        self.last_message_at = fields.Datetime.now()
        self.message_post(body=Markup("<b>Respuesta WhatsApp:</b> ") + escape(text), message_type="comment",
                          subtype_xmlid="mail.mt_note")
        return message.id


    def _can_reply_freely(self):
        self.ensure_one()
        return bool(self.last_inbound_at) and (fields.Datetime.now() - self.last_inbound_at).total_seconds() < 24 * 3600


class GsWhatsappMessage(models.Model):
    _name = "gs.whatsapp.message"
    _description = "WhatsApp message"
    _order = "id desc"

    conversation_id = fields.Many2one("gs.whatsapp.conversation", required=True, ondelete="cascade", index=True)
    direction = fields.Selection([("in", "Received"), ("out", "Sent")], required=True)
    wa_message_id = fields.Char(index=True)
    kind = fields.Char(default="text")
    body = fields.Text()
    attachment_id = fields.Many2one("ir.attachment")
    author_id = fields.Many2one("res.partner")

    _wa_id_unique = models.Constraint("UNIQUE(wa_message_id)", "Meta delivers a message only once.")

    def image_b64(self):
        self.ensure_one()
        return base64.b64encode(self.attachment_id.raw).decode() if self.attachment_id else None
