import hmac
import time

from markupsafe import escape

from odoo import http
from odoo.exceptions import UserError
from odoo.http import request

PENDING_KEY = "orca_bridge_oauth"
PENDING_TTL = 600


class OrcaBridgeOAuth(http.Controller):
    """OAuth 2.0 client side of the ORCA connector (authorization code + PKCE)."""

    def _page(self, title, message, ok):
        color = "#067647" if ok else "#b42318"
        html = (
            "<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{escape(title)}</title></head><body style='font-family:system-ui,sans-serif;max-width:560px;margin:48px auto;padding:0 16px'>"
            f"<h1 style='font-size:22px'>{escape(title)}</h1><p style='color:{color};font-weight:600' role='status'>{escape(message)}</p>"
            "<p><a href='/odoo/settings'>Volver a Ajustes</a></p></body></html>"
        )
        return request.make_response(html, headers=[("Content-Type", "text/html; charset=utf-8"), ("Cache-Control", "no-store")])

    def _check_admin(self):
        if not request.env.user.has_group("base.group_system"):
            raise request.not_found()

    @http.route("/orca_bridge/oauth/start", type="http", auth="user", methods=["GET"])
    def start(self):
        self._check_admin()
        try:
            url, pending = request.env["orca.bridge.client"]._authorize_url()
        except UserError as exc:
            return self._page("ORCA", str(exc), False)
        request.session[PENDING_KEY] = pending
        return request.redirect(url, local=False)

    @http.route("/orca_bridge/oauth/callback", type="http", auth="user", methods=["GET"])
    def callback(self, code=None, state=None, error=None, error_description=None, **kwargs):
        self._check_admin()
        pending = request.session.pop(PENDING_KEY, None)
        if error:
            return self._page("Conexion con ORCA cancelada", error_description or error, False)
        if (not pending or not state or not code or not hmac.compare_digest(str(state), pending.get("state", ""))
                or time.time() - pending.get("ts", 0) > PENDING_TTL):
            return self._page("Conexion con ORCA", "Solicitud vencida o no valida: vuelva a pulsar 'Conectar con ORCA'.", False)
        try:
            result = request.env["orca.bridge.client"]._complete_oauth(code, pending["verifier"])
        except UserError as exc:
            return self._page("Conexion con ORCA", str(exc), False)
        message = f"Odoo quedo conectado a ORCA ({result['company']}) como {result['connection_id']}."
        if not result.get("reachable"):
            message += " Atencion: ORCA no pudo llegar a este Odoo con la URL web.base.url; revise la URL publica."
        return self._page("Conectado a ORCA", message, True)
