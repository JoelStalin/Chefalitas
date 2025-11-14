# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class InvoiceServiceTypeDetail(models.Model):
    """
    Catálogo de tipos de servicio de la DGII para facturas.

    NOTA IMPORTANTE SOBRE TRADUCCIONES Y SQL CONSTRAINTS:
    -----------------------------------------------------
    - En _sql_constraints NO usamos _() ni _lt(), solo strings planos.
    - El mensaje traducible se gestiona vía ir.model.constraint y el .po.
    """
    _name = "invoice.service.type.detail"
    _description = "Invoice Service Type Detail"
    _rec_name = "code"

    # -------------------------------------------------------------------------
    # CAMPOS
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Descripción",
        required=True,
        help="Descripción legible del tipo de servicio."
    )

    code = fields.Char(
        string="Código",
        size=2,
        required=True,
        index=True,
        help="Código DGII de 2 caracteres para el tipo de servicio."
    )

    parent_code = fields.Char(
        string="Código Padre",
        help="Código padre (si aplica) según catálogo DGII."
    )

    # -------------------------------------------------------------------------
    # CONSTRAINTS SQL
    # -------------------------------------------------------------------------
    # Odoo creará automáticamente los índices y constraints en PostgreSQL
    # a partir de esta lista.
    _sql_constraints = [
        # Unicidad del código a nivel SQL
        (
            "invoice_service_type_detail_code_unique",
            "UNIQUE(code)",
            # ¡OJO! Aquí NO se usa _() ni _lt()
            "Code must be unique",
        ),

        # (Opcional) Validar longitud exacta 2 en SQL
        # Si no quieres esta restricción, borra esta línea.
        (
            "invoice_service_type_detail_code_length_check",
            "CHECK (char_length(code) = 2)",
            "Code must be exactly 2 characters",
        ),
    ]

    # -------------------------------------------------------------------------
    # CONSTRAINTS PYTHON (opcionales, para mensajes más amigables)
    # -------------------------------------------------------------------------

    @api.constrains("code")
    def _check_code_required(self):
        """Evita códigos vacíos desde lógica Python."""
        for rec in self:
            if not rec.code:
                raise ValidationError(_("Code is required"))

    @api.constrains("code")
    def _check_code_digits(self):
        """
        Opcional: obliga a que el código sea numérico.
        Si DGII publica códigos alfanuméricos, elimina este constraint.
        """
        for rec in self:
            if rec.code and not rec.code.isdigit():
                raise ValidationError(_("Code must contain only digits"))
