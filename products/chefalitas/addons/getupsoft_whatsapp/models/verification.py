"""Credentials of the Meta account and confirmation codes (GetUpSoft code).

- Secrets (Meta password, Google refresh token) are stored encrypted (Fernet) with a key derived from the
  database secret; only system administrators can read or set them.
- A company mailbox is linked with Google's OAuth consent (Gmail, read only): confirmation codes Meta sends by
  e-mail are found automatically.
- Codes sent by SMS (or any other channel) are asked over WhatsApp to the person in charge, from an account that is
  already connected; the reply "codigo 123456" is captured, or the code is typed in the form.
Works without ORCA; ORCA automates the Meta setup by calling request_code / the code requests.
"""
import base64
import hashlib
import logging
import re
import secrets
from datetime import timedelta
from urllib.parse import urlencode

import requests
from cryptography.fernet import Fernet, InvalidToken

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me"
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
CODE = re.compile(r"(?<!\d)(\d{4,8})(?!\d)")
REPLY = re.compile(r"^\s*(?:c[oó]digo|code)?\s*[:\-]?\s*(\d{4,8})\s*$", re.I)


def _fernet(env):
    secret = env["ir.config_parameter"].sudo().get_str("database.secret") or env.cr.dbname
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(f"gs-whatsapp:{secret}".encode()).digest()))


def encrypt(env, value):
    return _fernet(env).encrypt(value.encode()).decode() if value else False


def decrypt(env, token):
    if not token:
        return ""
    try:
        return _fernet(env).decrypt(token.encode()).decode()
    except InvalidToken:
        _logger.warning("getupsoft_whatsapp: a stored secret cannot be decrypted (database secret changed?)")
        return ""


class GsMailInbox(models.Model):
    """Company mailbox (Gmail) used to receive confirmation codes."""

    _name = "gs.mail.inbox"
    _description = "Mailbox for confirmation codes"

    name = fields.Char(required=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    email = fields.Char(readonly=True)
    google_client_id = fields.Char("Google OAuth client ID")
    google_client_secret_enc = fields.Char(groups="base.group_system", copy=False)
    google_client_secret = fields.Char("Google OAuth client secret", compute="_compute_secret", inverse="_inverse_secret",
                                       groups="base.group_system")
    refresh_token_enc = fields.Char(groups="base.group_system", copy=False)
    oauth_state = fields.Char(groups="base.group_system", copy=False)
    connected = fields.Boolean(compute="_compute_connected")

    def _compute_secret(self):
        for inbox in self:
            inbox.google_client_secret = "********" if inbox.sudo().google_client_secret_enc else False

    def _inverse_secret(self):
        for inbox in self:
            if inbox.google_client_secret and inbox.google_client_secret != "********":
                inbox.sudo().google_client_secret_enc = encrypt(self.env, inbox.google_client_secret)

    def _compute_connected(self):
        for inbox in self:
            inbox.connected = bool(inbox.sudo().refresh_token_enc)

    def _redirect_uri(self):
        base = (self.env["ir.config_parameter"].sudo().get_str("web.base.url") or "").rstrip("/")
        return f"{base}/getupsoft_whatsapp/google/callback"

    def action_connect_google(self):
        """Google's OAuth consent screen (Gmail read only, offline access)."""
        self.ensure_one()
        if not (self.google_client_id and self.sudo().google_client_secret_enc):
            raise UserError(_("Fill in the Google OAuth client ID and secret first."))
        state = f"{self.id}:{secrets.token_urlsafe(24)}"
        self.sudo().oauth_state = state
        url = f"{GOOGLE_AUTH}?" + urlencode({
            "client_id": self.google_client_id, "redirect_uri": self._redirect_uri(), "response_type": "code",
            "scope": GMAIL_SCOPE, "access_type": "offline", "prompt": "consent", "state": state})
        return {"type": "ir.actions.act_url", "url": url, "target": "self"}

    def _google_complete(self, code):
        self.ensure_one()
        tokens = requests.post(GOOGLE_TOKEN, timeout=20, data={
            "code": code, "client_id": self.google_client_id, "client_secret": decrypt(self.env, self.sudo().google_client_secret_enc),
            "redirect_uri": self._redirect_uri(), "grant_type": "authorization_code"}).json()
        if "refresh_token" not in tokens:
            raise UserError(_("Google did not return a refresh token: %s", tokens.get("error_description", tokens)))
        profile = requests.get(f"{GMAIL}/profile", timeout=20,
                               headers={"Authorization": f"Bearer {tokens['access_token']}"}).json()
        self.sudo().write({"refresh_token_enc": encrypt(self.env, tokens["refresh_token"]),
                           "email": profile.get("emailAddress"), "oauth_state": False})
        return True

    def _access_token(self):
        self.ensure_one()
        data = requests.post(GOOGLE_TOKEN, timeout=20, data={
            "client_id": self.google_client_id, "client_secret": decrypt(self.env, self.sudo().google_client_secret_enc),
            "refresh_token": decrypt(self.env, self.sudo().refresh_token_enc), "grant_type": "refresh_token"}).json()
        if "access_token" not in data:
            raise UserError(_("Google refused the mailbox token: %s", data.get("error_description", data)))
        return data["access_token"]

    def _find_code(self, sender_query, after):
        """Newest code in a message matching the Gmail query, received after `after` (datetime)."""
        self.ensure_one()
        headers = {"Authorization": f"Bearer {self._access_token()}"}
        query = f"{sender_query} after:{int(after.timestamp())}"
        found = requests.get(f"{GMAIL}/messages", headers=headers, timeout=20, params={"q": query, "maxResults": 5}).json()
        for ref in found.get("messages", []):
            msg = requests.get(f"{GMAIL}/messages/{ref['id']}", headers=headers, timeout=20,
                               params={"format": "full"}).json()
            text = " ".join([msg.get("snippet", "")] + [_decode(p) for p in _parts(msg.get("payload", {}))])
            match = CODE.search(re.sub(r"<[^>]+>", " ", text))
            if match:
                return match.group(1)
        return None


def _parts(payload):
    yield payload
    for part in payload.get("parts", []) or []:
        yield from _parts(part)


def _decode(part):
    data = (part.get("body") or {}).get("data")
    if not data or not str(part.get("mimeType", "")).startswith("text/"):
        return ""
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "ignore")


class GsVerificationRequest(models.Model):
    """A confirmation code the Meta setup is waiting for."""

    _name = "gs.verification.request"
    _description = "Confirmation code request"
    _order = "id desc"

    account_id = fields.Many2one("gs.whatsapp.account", required=True, ondelete="cascade")
    purpose = fields.Char(required=True, default="Meta")
    channel = fields.Selection([("email", "Correo"), ("sms", "SMS"), ("other", "Otro")], required=True)
    state = fields.Selection([("pending", "Esperando código"), ("received", "Recibido"), ("expired", "Vencido")],
                             default="pending", required=True)
    code = fields.Char(groups="base.group_system")
    asked_conversation_id = fields.Many2one("gs.whatsapp.conversation", readonly=True)
    expires_at = fields.Datetime(default=lambda self: fields.Datetime.now() + timedelta(minutes=15))

    def _check_mailbox(self):
        """Email codes: look in the company mailbox (Gmail)."""
        for req in self.filtered(lambda r: r.state == "pending" and r.channel == "email"):
            inbox = req.account_id.code_inbox_id
            if not inbox or not inbox.connected:
                continue
            code = inbox._find_code(req.account_id.meta_code_query or "from:(facebookmail.com OR meta.com)", req.create_date)
            if code:
                req.write({"code": code, "state": "received"})
        return self

    def _set_code(self, code):
        self.ensure_one()
        self.write({"code": code, "state": "received"})

    def action_enter_code(self):
        """Form: the person types the code they received."""
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id, "view_mode": "form", "target": "new"}

    @api.model
    def _expire(self):
        self.search([("state", "=", "pending"), ("expires_at", "<", fields.Datetime.now())]).write({"state": "expired"})


class GsWhatsappAccount(models.Model):
    _inherit = "gs.whatsapp.account"

    meta_email = fields.Char("Meta account e-mail", groups="base.group_system")
    meta_password_enc = fields.Char(groups="base.group_system", copy=False)
    meta_password = fields.Char("Meta account password", compute="_compute_meta_password",
                                inverse="_inverse_meta_password", groups="base.group_system")
    meta_sms_number = fields.Char("Number that receives Meta SMS codes")
    code_inbox_id = fields.Many2one("gs.mail.inbox", "Mailbox for e-mail codes")
    meta_code_query = fields.Char("Gmail search for Meta codes", default="from:(facebookmail.com OR meta.com)")
    notify_account_id = fields.Many2one("gs.whatsapp.account", "Ask codes through",
                                        help="A connected WhatsApp account used to ask the person in charge for codes")
    notify_number = fields.Char("WhatsApp of the person in charge")
    code_request_ids = fields.One2many("gs.verification.request", "account_id")

    def _compute_meta_password(self):
        for account in self:
            account.meta_password = "********" if account.sudo().meta_password_enc else False

    def _inverse_meta_password(self):
        for account in self:
            if account.meta_password and account.meta_password != "********":
                account.sudo().meta_password_enc = encrypt(self.env, account.meta_password)

    def _meta_credentials(self):
        """For the automated Meta setup (ORCA / browser automation): e-mail and decrypted password."""
        self.ensure_one()
        return {"email": self.sudo().meta_email, "password": decrypt(self.env, self.sudo().meta_password_enc)}

    def request_code(self, channel, purpose="Meta"):
        """Start waiting for a confirmation code. E-mail: read from the mailbox. SMS/other: ask over WhatsApp.
        Returns the request id; poll get_code(request_id). Public: ORCA calls it through the JSON-2 API."""
        self.ensure_one()
        req = self.env["gs.verification.request"].create({"account_id": self.id, "channel": channel, "purpose": purpose})
        if channel == "email":
            if not (self.code_inbox_id and self.code_inbox_id.connected):
                raise UserError(_("Connect a mailbox (Google) to receive e-mail codes."))
            req._check_mailbox()
            return req.id
        notifier = self.notify_account_id
        if not (notifier and notifier.state == "connected" and self.notify_number):
            raise UserError(_("Set a connected WhatsApp account and the number of the person in charge to ask for codes."))
        where = _("por SMS al %s", self.meta_sms_number) if channel == "sms" and self.meta_sms_number else _("por %s", channel)
        conv = self.env["gs.whatsapp.conversation"]._for_number(notifier, self.notify_number)
        conv.send_text(_("%(purpose)s envió un código de confirmación %(where)s. Responda a este mensaje con: codigo 123456 "
                         "(o escríbalo en Odoo > WhatsApp > Configuración).", purpose=purpose, where=where))
        req.asked_conversation_id = conv
        return req.id

    def get_code(self, request_id):
        """The code once received (None while waiting). E-mail requests check the mailbox on each call."""
        self.ensure_one()
        req = self.env["gs.verification.request"].browse(request_id).exists()
        if not req or req.account_id != self:
            raise UserError(_("Unknown code request."))
        self.env["gs.verification.request"]._expire()
        if req.state == "pending":
            req._check_mailbox()
        return req.sudo().code if req.state == "received" else None


class GsWhatsappConversationCodes(models.Model):
    _inherit = "gs.whatsapp.conversation"

    def _on_inbound(self, message):
        """A reply 'codigo 123456' fills the code request that was asked in this conversation."""
        match = REPLY.match(message.body or "")
        if match:
            req = self.env["gs.verification.request"].sudo().search(
                [("asked_conversation_id", "=", self.id), ("state", "=", "pending")], limit=1, order="id desc")
            if req:
                req._set_code(match.group(1))
                self.send_text(_("Código recibido. Gracias."))
                return req
        return super()._on_inbound(message)
