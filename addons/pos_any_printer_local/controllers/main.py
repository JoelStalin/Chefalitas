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
        Sirve el instalador del agente local directamente desde el módulo.

        Nota: para archivos binarios grandes es preferible delegar a nginx u otro
        servidor web, pero mantenemos este enfoque para simplicidad en entornos
        de pruebas/PoC.
        """

        module_path = get_module_path('pos_any_printer_local')

        if not module_path:
            raise werkzeug.exceptions.NotFound("Módulo 'pos_any_printer_local' no encontrado.")

        file_path = os.path.join(
            module_path,
            'static',
            'download',
            'agent_local',
            # 'dist',
            'LocalPrinterAgent.exe'
        )

        if not os.path.exists(file_path):
            raise werkzeug.exceptions.NotFound("El archivo 'LocalPrinterAgent.exe' no se encuentra en la ruta esperada.")

        try:
            with open(file_path, 'rb') as f:
                file_content = f.read()

            file_name = 'LocalPrinterAgent.exe'
            headers = [
                ('Content-Type', 'application/octet-stream'),
                ('Content-Disposition', http.content_disposition(file_name)),
                ('Content-Length', len(file_content)),
            ]

            return request.make_response(file_content, headers)

        except Exception as e:  # pragma: no cover - logging handled by Odoo
            return request.make_response(
                f"Error al leer el archivo: {str(e)}",
                status=500,
            )
