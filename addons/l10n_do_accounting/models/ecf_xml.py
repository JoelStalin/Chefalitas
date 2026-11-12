"""Lectura del XML e-CF firmado, sin dependencias de Odoo (se prueba en tests/standalone)."""
import re


def signed_tag(xml, tag):
    """Valor exacto de <tag> en el XML firmado, o None.

    Coincide solo con la etiqueta completa: <MontoTotal> no toma <MontoTotalOtraMoneda>.
    """
    if not xml:
        return None
    if isinstance(xml, bytes):
        xml = xml.decode("utf-8", "replace")
    found = re.search(r"<%s>([^<]+)</%s>" % (re.escape(tag), re.escape(tag)), xml)
    return found.group(1).strip() if found else None


def signed_monto_total(xml):
    """MontoTotal tal como lo firmó el emisor: la DGII lo compara literal en ConsultaTimbre."""
    return signed_tag(xml, "MontoTotal")


def signed_sign_stamp(xml):
    """FechaHoraFirma tal como se firmó (dd-mm-aaaa HH:MM:SS, hora RD)."""
    return signed_tag(xml, "FechaHoraFirma")
