import io
import json
import os
import secrets
import zipfile
from urllib.parse import urlparse

from odoo import http
from odoo.http import request

PLUGIN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "plugin")
FILES = ("AnyPrinter.ps1", "instalar.bat", "desinstalar.bat", "abrir_caja.bat", "capturar_bascula.bat", "capturar_bascula.ps1", "LEEME.txt")


class AnyPrinterController(http.Controller):
    def _token(self):
        icp = request.env["ir.config_parameter"].sudo()
        token = icp.get_str("orca_printer.token")
        if not token:
            token = secrets.token_urlsafe(24)
            icp.set_str("orca_printer.token", token)
        return token

    @http.route("/orca_printer/download", type="http", auth="user")
    def download(self, **kw):
        if not request.env.user.has_group("point_of_sale.group_pos_manager"):
            return request.not_found()
        base = request.env["ir.config_parameter"].sudo().get_str("web.base.url") or request.httprequest.host_url
        u = urlparse(base)
        origins = sorted({f"{u.scheme}://{u.netloc}", request.httprequest.host_url.rstrip("/")})
        cfg = {"port": 9050, "port_cocina": 9051, "token": self._token(), "origins": origins, "printer": "", "roles": {"caja": "", "cocina": ""}, "drawer_pin": 0}
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for name in FILES:
                with open(os.path.join(PLUGIN_DIR, name), "rb") as f:
                    z.writestr("AnyPrinter/" + name, f.read())
            z.writestr("AnyPrinter/config.json", json.dumps(cfg, indent=2))
        return request.make_response(buf.getvalue(), headers=[
            ("Content-Type", "application/zip"),
            ("Content-Disposition", 'attachment; filename="AnyPrinter.zip"'),
        ])
