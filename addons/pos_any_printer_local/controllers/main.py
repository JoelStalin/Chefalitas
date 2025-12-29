# -*- coding: utf-8 -*-
import os
from odoo import http
from odoo.http import request
from odoo.modules import get_module_path
import werkzeug


class FileDownloadController(http.Controller):

    @http.route('/download/agent', type='http', auth='user', csrf=False)
    def download_agent_file(self, **kw):
        """
        Sirve el instalador del agente local desde el módulo.

        Preferencia de entrega:
        1) LocalPrinterAgent-Setup.exe (instalable con UAC y tareas postinstalación)
        2) LocalPrinterAgent.exe (binario standalone)
        """

        module_path = get_module_path('pos_any_printer_local')
        if not module_path:
            raise werkzeug.exceptions.NotFound("Módulo 'pos_any_printer_local' no encontrado.")

        base_dir = os.path.join(module_path, 'static', 'download')
        candidates = [
            ('LocalPrinterAgent-Setup.exe', 'application/vnd.microsoft.portable-executable'),
            ('LocalPrinterAgent.exe', 'application/vnd.microsoft.portable-executable'),
        ]

        file_path = None
        file_name = None
        content_type = 'application/octet-stream'

        for name, ctype in candidates:
            p = os.path.join(base_dir, name)
            if os.path.exists(p):
                file_path = p
                file_name = name
                content_type = ctype
                break

        if not file_path:
            raise werkzeug.exceptions.NotFound(
                "No se encontró un instalador en static/download/. Coloque 'LocalPrinterAgent-Setup.exe' o 'LocalPrinterAgent.exe'."
            )

        try:
            with open(file_path, 'rb') as f:
                file_content = f.read()

            headers = [
                ('Content-Type', content_type),
                ('Content-Disposition', http.content_disposition(file_name)),
                ('Content-Length', len(file_content)),
            ]

            return request.make_response(file_content, headers)

        except Exception as e:  # pragma: no cover - logging handled by Odoo
            return request.make_response(
                f"Error al leer el archivo: {str(e)}",
                status=500,
            )

