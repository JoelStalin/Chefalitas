"""Pruebas sin Odoo de la lectura del XML e-CF firmado (monto y fecha que van en el QR)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "models"))

from ecf_xml import signed_monto_total, signed_sign_stamp, signed_tag

# Caso real E310000000004: Odoo totaliza 234534.91, el XML firmado dice 234534.90 y la DGII
# solo encuentra la factura con el monto del XML.
XML = (
    '<?xml version="1.0" encoding="utf-8"?><ECF><Encabezado><Totales>'
    "<MontoGravadoTotal>198758.39</MontoGravadoTotal><TotalITBIS>35776.51</TotalITBIS>"
    "<MontoTotal>234534.90</MontoTotal></Totales>"
    "<OtraMoneda><MontoTotalOtraMoneda>4100.00</MontoTotalOtraMoneda></OtraMoneda>"
    "</Encabezado><DetallesItems><Item><MontoItem>75257.37</MontoItem></Item></DetallesItems>"
    "<FechaHoraFirma>10-11-2026 14:17:37</FechaHoraFirma></ECF>"
)


class SignedXmlTests(unittest.TestCase):
    def test_monto_total_is_the_signed_string(self):
        self.assertEqual(signed_monto_total(XML), "234534.90")

    def test_monto_total_ignores_other_currency_tag(self):
        xml = "<ECF><MontoTotalOtraMoneda>10.00</MontoTotalOtraMoneda><MontoTotal>59.00</MontoTotal></ECF>"
        self.assertEqual(signed_monto_total(xml), "59.00")

    def test_sign_stamp(self):
        self.assertEqual(signed_sign_stamp(XML), "10-11-2026 14:17:37")

    def test_bytes_input(self):
        self.assertEqual(signed_monto_total(XML.encode()), "234534.90")

    def test_missing_or_empty(self):
        self.assertIsNone(signed_monto_total(None))
        self.assertIsNone(signed_monto_total(""))
        self.assertIsNone(signed_tag("<ECF></ECF>", "MontoTotal"))


if __name__ == "__main__":
    unittest.main()
