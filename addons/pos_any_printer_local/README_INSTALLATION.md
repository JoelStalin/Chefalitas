# POS Local Printer - Instalación e instrucciones

Este documento explica cómo instalar el módulo Odoo y el agente local en la máquina del cajero.

## 1) Módulo Odoo
1. Copia la carpeta `pos_any_printer_local` en el directorio `addons/` de tu instalación de Odoo.
2. Reinicia el servidor Odoo.
3. Ve a Apps y actualiza la lista de aplicaciones.
4. Instala **POS Local Printer (search by name)**.
5. En Punto de Venta -> Configuración -> Elige tu POS y rellena el campo **Nombre impresora local** con exactamente el nombre tal como aparece en la máquina del cajero (puedes usar la UI de agente para ver nombres).

## 2) Agente local (máquina del cajero)
### Requisitos
- Python 3.8+ (recomendado)
- pip install flask flask-cors
- En Windows: pip install pywin32
- En Linux: `cups` y utilidades `lp`/`lpr` (CUPS)

### Pasos rápidos
1. Copia `agent/printer_agent.py` en la máquina del cajero.
2. Instala dependencias:
   - Linux: `pip3 install flask flask-cors pycups` (pycups opcional si lpstat falla)
   - Windows: `pip install flask flask-cors pywin32`
3. Prueba ejecutar: `python3 printer_agent.py`
4. Abre en el navegador (en la misma máquina): `http://127.0.0.1:9100/printers` — verás JSON con impresoras.

### Ejecutar en segundo plano (Linux systemd)
Crear archivo `/etc/systemd/system/pos-printer-agent.service`:
```
[Unit]
Description=POS Local Printer Agent
After=network.target

[Service]
User=youruser
WorkingDirectory=/home/youruser/pos_any_printer_local/agent
ExecStart=/usr/bin/python3 /home/youruser/pos_any_printer_local/agent/printer_agent.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Luego:
```
sudo systemctl daemon-reload
sudo systemctl enable pos-printer-agent
sudo systemctl start pos-printer-agent
sudo systemctl status pos-printer-agent
```

### Ejecutar en Windows (como servicio)
- Opción simple: usar NSSM (https://nssm.cc/) para registrar `python.exe C:\path\to\printer_agent.py` como servicio.
- Opción alternativa: crear un ejecutable con PyInstaller y usar el Programador de tareas o NSSM.

## 3) Firewall
Asegúrate que la máquina permita conexiones a `127.0.0.1:9100` desde el navegador local (normalmente no hay bloqueo). No expongas el agente a la red pública.

## 4) Integración y pruebas
1. Abre el POS en la máquina del cajero (el navegador donde corre el POS).
2. El JS del módulo intentará verificar el agente local al iniciar. Revisa la consola del navegador para ver logs.
3. Genera un ticket e intenta imprimir. Si el formato es raw ESC/POS, manda bytes; si envías PDF, el agente usará `lp`/`lpr`.

## 5) Seguridad
- Limita CORS si lo deseas cambiando `CORS(app, origins="*")` a `CORS(app, origins=["http://localhost:8069"])` o similar.
- Considera un token compartido (header) entre POS y agent para evitar que cualquier web lo use.

## 6) Fallbacks
- Si el agente no está presente, el módulo no romperá el POS; implementa tu lógica de fallback (QZ Tray, impresión por servidor, etc.).


## Selector de impresora desde POS
En el POS, puedes abrir el selector de impresoras detectadas pulsando Ctrl+P (o Cmd+P en macOS) en la ventana del POS.
El selector listará las impresoras detectadas por el agente local y guardará la selección en la configuración del POS.
