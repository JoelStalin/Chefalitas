import base64
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _xml_bytes(value):
    """Bytes del XML e-CF guardado, venga como venga el Binary.

    Odoo 20 devuelve un BinaryValueAttachment (bytes en `.content`), no bytes: eso
    rompió la primera versión de esta migración. Se aceptan también bytes/str
    crudos o en base64.
    """
    if not value:
        return None
    raw = getattr(value, "content", value)
    if isinstance(raw, str):
        raw = raw.encode()
    if not isinstance(raw, (bytes, bytearray)):
        raw = bytes(raw)
    if b"<" in raw[:200]:
        return raw
    try:
        return base64.b64decode(raw, validate=True)
    except Exception:  # noqa: BLE001 - un XML ilegible no debe frenar la migracion
        return raw


def migrate(cr, version):
    """Rellena el MontoTotal firmado de los e-CF ya emitidos y recalcula su QR.

    Antes el QR usaba el total de Odoo; si el XML firmado tenia otro redondeo
    (p. ej. E310000000004: 234534.91 en Odoo, 234534.90 firmado) la DGII
    respondia "No fue encontrada la factura".
    """
    from odoo.addons.l10n_do_accounting.models.ecf_xml import signed_monto_total, signed_sign_stamp

    env = api.Environment(cr, SUPERUSER_ID, {})
    moves = env["account.move"].with_context(active_test=False).search([
        ("l10n_do_ecf_edi_file", "!=", False),
        ("l10n_do_ecf_monto_total", "=", False),
    ])
    for move in moves:
        try:
            xml = _xml_bytes(move.l10n_do_ecf_edi_file)
        except Exception as exc:  # noqa: BLE001 - un asiento raro no debe frenar el despliegue
            _logger.warning("e-CF %s: no se pudo leer el XML (%s)", move.name, exc)
            continue
        vals = {}
        monto = signed_monto_total(xml)
        if monto:
            vals["l10n_do_ecf_monto_total"] = monto
        if not move.l10n_do_ecf_sign_stamp:
            stamp = signed_sign_stamp(xml)
            if stamp:
                vals["l10n_do_ecf_sign_stamp"] = stamp
        if vals:
            move.write(vals)
            _logger.info("e-CF %s: QR recalculado con MontoTotal firmado %s", move.name, monto)
