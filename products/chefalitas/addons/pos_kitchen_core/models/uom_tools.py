from odoo import api, models


class UoMTools(models.AbstractModel):
    _name = "rest.uom.tools"
    _description = "Kitchen UoM Tools"

    @api.model
    def convert_to_grams(self, qty, uom):
        if not uom:
            return qty
        gram_uom = self.env.ref("uom.product_uom_gram", raise_if_not_found=False)
        if not gram_uom:
            return qty
        return uom._compute_quantity(qty, gram_uom)

    @api.model
    def convert_from_grams(self, qty, uom):
        if not uom:
            return qty
        gram_uom = self.env.ref("uom.product_uom_gram", raise_if_not_found=False)
        if not gram_uom:
            return qty
        return gram_uom._compute_quantity(qty, uom)
