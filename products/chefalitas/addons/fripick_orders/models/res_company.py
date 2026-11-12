from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    fripick_external_id = fields.Char("Fripick ID", index=True, copy=False,
                                      help="Identifier of this company in Fripick; the daily sync matches on it.")
    fripick_invoice_issuer = fields.Selection(
        [("fripick", "Fripick factura"), ("company", "La empresa factura")], default="company", required=True,
        string="Quién emite la factura mensual",
        help="Fripick: the Fripick company invoices this company. Empresa: this company invoices Fripick.")
    fripick_partner_id = fields.Many2one("res.partner", string="Contacto Fripick",
                                         help="Fripick as a customer/vendor partner for the monthly invoice.")
    # the POS printers of pos_printing_suite (network discovery, agent or cloud gateway): one printer model for everything
    fripick_kitchen_printer_id = fields.Many2one("pos.printer", string="Impresora de cocina",
                                                 domain="[('company_id', 'in', (id, False))]")
    fripick_cashier_printer_id = fields.Many2one("pos.printer", string="Impresora de caja",
                                                 domain="[('company_id', 'in', (id, False))]")
    fripick_labels_enabled = fields.Boolean("Imprimir etiquetas Fripick en caja")
    fripick_label_format = fields.Selection([("fripick", "Formato Fripick (80 mm)"), ("a4", "Estándar A4")],
                                            default="fripick", required=True, string="Formato de etiqueta")
    fripick_last_sync = fields.Datetime("Última sincronización Fripick", readonly=True)
