from re import compile
from odoo import models, fields, _
from odoo.exceptions import ValidationError


class L10nLatamDocumentType(models.Model):
    _inherit = "l10n_latam.document.type"

    def _get_l10n_do_ncf_types(self):
        """Retorna los tipos de comprobantes fiscales (NCF/ECF) utilizados en República Dominicana."""
        return [
            ("fiscal", "01"),
            ("consumer", "02"),            # Consumo
            ("debit_note", "03"),          # Nota de Débito
            ("credit_note", "04"),         # Nota de Crédito
            ("informal", "11"),            # Proveedores informales
            ("unique", "12"),              # Regímenes únicos de tributación
            ("minor", "13"),               # Gastos menores
            ("special", "14"),             # Rentas presuntas
            ("governmental", "15"),        # Gubernamentales
            ("export", "16"),              # Exportaciones
            ("exterior", "17"),            # Pagos al exterior
            ("e-fiscal", "31"),
            ("e-consumer", "32"),
            ("e-debit_note", "33"),
            ("e-credit_note", "34"),
            ("e-informal", "41"),
            ("e-minor", "43"),
            ("e-special", "44"),
            ("e-governmental", "45"),
            ("e-export", "46"),
            ("e-exterior", "47"),
            ("in_fiscal", "01"),  # Interno, mismo que fiscal
        ]
        
    l10n_do_company_in_contingency = fields.Boolean("Empresa en contingencia")
    
    l10n_do_ncf_type = fields.Selection(
        selection="_get_l10n_do_ncf_types",
        string="Tipo de NCF",
        help="Tipos de comprobantes fiscales definidos por la DGII para identificar "
             "documentos según el tipo de operación y las responsabilidades del emisor y receptor.",
    )

    l10n_do_ncf_expiration_date = fields.Date(
        string="Fecha de vencimiento del NCF",
        required=True,
        default=lambda self: fields.Date.end_of(fields.Date.today(), "year"),
        help="(Obsoleto) Fecha de expiración del NCF. No debe portarse a versiones futuras.",
    )

    internal_type = fields.Selection(
        selection_add=[
            ("in_invoice", "Factura de proveedor"),
            ("in_credit_note", "Nota de crédito de proveedor"),
            ("in_debit_note", "Nota de débito de proveedor"),
        ],
        ondelete={
            "in_invoice": "cascade",
            "in_credit_note": "cascade",
            "in_debit_note": "cascade",
        },
    )

    is_vat_required = fields.Boolean(
        string="¿Requiere ITBIS?",
        default=False,
    )

    def _format_document_number(self, document_number):
        """Valida y formatea un número de NCF/ECF basado en la estructura DGII 2025."""
        self.ensure_one()

        if self.country_id != self.env.ref("base.do"):
            # Si no es República Dominicana, usar validación original
            return super()._format_document_number(document_number)

        if not document_number:
            return False

        # Obtener el código del tipo de NCF (ej. "31", "04", etc.)
        ncf_code = dict(self._get_l10n_do_ncf_types()).get(self.l10n_do_ncf_type)
        if not ncf_code:
            raise ValidationError(_("El tipo de NCF seleccionado no es válido o no está definido."))

        # Expresión regular según normativas 2025:
        # ECF: E + tipo + 10 dígitos = 13 caracteres
        # NCF físico: B + tipo + 8 dígitos = 11 caracteres
        # Opcionalmente se permite el prefijo P para preimpresos: PE / PB
        regex = (
            r"^(P?)"                       # Prefijo opcional "P"
            r"([EB])"                      # Debe comenzar con E o B
            r"%s"                          # Código del tipo (ej. 31, 02)
            r"(\d{10}|\d{8})$"             # 10 dígitos si es E, 8 si es B
        ) % ncf_code

        pattern = compile(regex)

        if not pattern.match(document_number):
            raise ValidationError(
                _("El NCF '%s' no cumple con la estructura establecida por la DGII para el tipo '%s'.") %
                (document_number, self.l10n_do_ncf_type)
            )

        return document_number
