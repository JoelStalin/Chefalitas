# -*- coding: utf-8 -*-
import os
import odoo
from odoo import http
from odoo.http import request
from odoo.modules import get_module_path
import werkzeug

class FileDownloadController(http.Controller):

    @http.route('/download/agent_file', type='http', auth='user', csrf=False)
    def download_agent_file(self, **kw):
        """
        Este controlador lee el archivo desde el disco y lo sirve directamente.
        Esto es INEFICIENTE para archivos estáticos.
        """
        
        # 1. Encontrar la ruta del módulo 'pos_any_printer_local'
        #    Esto asume que dicho módulo está instalado.
        module_name = 'pos_any_printer_local'
        module_path = get_module_path(module_name)
        
        if not module_path:
            # Si el módulo no se encuentra, devuelve un error 404
            raise werkzeug.exceptions.NotFound("Módulo 'pos_any_printer_local' no encontrado.")

        # 2. Construir la ruta completa al archivo
        file_path = os.path.join(
            module_path, 
            'static', 
            'download', 
            'agent_local', 
            'dist', 
            'LocalPrinterAgent.exe'
        )

        # 3. Verificar si el archivo existe
        if not os.path.exists(file_path):
            raise werkzeug.exceptions.NotFound("El archivo 'LocalPrinterAgent.exe' no se encuentra en la ruta esperada.")

        try:
            # 4. Leer el contenido del archivo en modo binario
            with open(file_path, 'rb') as f:
                file_content = f.read()

            # 5. Preparar las cabeceras (headers) para la descarga
            file_name = 'LocalPrinterAgent.exe'
            headers = [
                ('Content-Type', 'application/octet-stream'), # Tipo genérico para binario
                ('Content-Disposition', http.content_disposition(file_name)), # Sugiere el nombre de archivo
                ('Content-Length', len(file_content)), # Informa al navegador el tamaño
            ]

            # 6. Devolver la respuesta
            return request.make_response(file_content, headers)

        except Exception as e:
            # Manejar cualquier error de lectura
            return request.make_response(
                f"Error al leer el archivo: {str(e)}", 
                status=500
            )