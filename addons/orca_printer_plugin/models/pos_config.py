import base64
import hashlib

from odoo import models, tools

# Un logo propio pesa mucho más que esto; los marcadores de posición en blanco (1x1) pesan unos pocos bytes.
MIN_REAL_LOGO_BYTES = 300


def _default_logo_md5():
    with tools.file_open("base/static/img/res_company_logo.png", "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def _raw_bytes(value):
    content = getattr(value, "content", value)
    if isinstance(content, str):
        content = content.encode()
    try:
        return base64.b64decode(content)
    except Exception:
        return content if isinstance(content, bytes) else b""


class PosConfig(models.Model):
    _inherit = "pos.config"

    def _compute_custom_info(self):
        """Si el usuario no configuró un logo propio, el recibo no imprime el logo de ejemplo de Odoo."""
        super()._compute_custom_info()
        default_md5 = _default_logo_md5()
        for config in self:
            if not config.logo:
                continue
            data = _raw_bytes(config.logo)
            if len(data) < MIN_REAL_LOGO_BYTES or hashlib.md5(data).hexdigest() == default_md5:
                config.logo = False
