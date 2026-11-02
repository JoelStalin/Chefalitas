from lxml import etree
from odoo.exceptions import ValidationError
import base64

def _validate_ecf_xml_schema(self):
    self.ensure_one()
    if not self.l10n_do_ecf_edi_file:
        return

    # Ruta al archivo XSD (debes cargarlo a tu módulo)
    xsd_path = get_module_resource('l10n_do_accounting', 'static', 'xsd', 'ECFv1_3.xsd')
    with open(xsd_path, 'rb') as f:
        schema_doc = etree.XML(f.read())
        schema = etree.XMLSchema(schema_doc)

    try:
        xml = base64.b64decode(self.l10n_do_ecf_edi_file)
        doc = etree.XML(xml)
        schema.assertValid(doc)
    except Exception as e:
        raise ValidationError(_("El archivo XML e-CF no es válido: %s") % str(e))
