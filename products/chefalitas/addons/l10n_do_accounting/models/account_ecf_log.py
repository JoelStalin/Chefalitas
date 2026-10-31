from odoo import models, fields, api

class AccountEcfLog(models.Model):
    _name = 'account.ecf.log'
    _description = 'Log de e-CF enviado a la DGII'

    move_id = fields.Many2one('account.move', string="Factura", required=True)
    state = fields.Selection([
        ('sent', 'Enviado'),
        ('accepted', 'Aceptado'),
        ('error', 'Error'),
    ], string="Estado", required=True)
    uuid = fields.Char("UUID", readonly=True)
    response_message = fields.Text("Mensaje DGII")
    date_sent = fields.Datetime("Fecha Envío", default=fields.Datetime.now)
