from odoo import models


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    def message_post(self, *args, **kwargs):
        inbound = kwargs.get("whatsapp_inbound_msg_uid")
        message = super().message_post(*args, **kwargs)
        if inbound and self.channel_type == "whatsapp":
            self.env["purchase.intake"].sudo()._on_whatsapp_message(self, message)
        return message
