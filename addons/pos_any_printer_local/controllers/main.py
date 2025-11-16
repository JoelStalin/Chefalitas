# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

class RedirectDownloadController(http.Controller):

    @http.route('/download/agent', type='http', auth='user', website=True)
    def redirect_to_agent_installer(self, **kw):
        """
        Este controlador redirige de forma inteligente a la URL estática del instalador.
        Esta es la forma eficiente y recomendada de gestionar una URL de descarga
        personalizada en Odoo.
        """

        # La URL estática apunta al instalador completo, no al .exe crudo.
        static_url = "/pos_any_printer_local/static/download/LocalPrinterAgent-Setup.exe"

        # Devuelve una redirección HTTP 302 (temporal), que es el estándar
        # para este tipo de operaciones.
        return request.redirect(static_url)
