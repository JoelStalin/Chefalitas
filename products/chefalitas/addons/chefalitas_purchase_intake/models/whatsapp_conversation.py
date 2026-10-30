from odoo import models


class GsWhatsappConversation(models.Model):
    _inherit = "gs.whatsapp.conversation"

    def _on_inbound(self, message):
        res = super()._on_inbound(message)
        intake = self.env["purchase.intake"].sudo()._on_whatsapp_message(self, message)
        return intake or res
