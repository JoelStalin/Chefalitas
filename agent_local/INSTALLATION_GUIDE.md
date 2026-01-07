# LocalPrinterAgent — Guía de Instalación y Uso

## Requisitos

- Windows 10+
- Python 3.8+ en PATH
- Permisos de Administrador (para instalar/administrar el servicio)

## Instalación

### Paso 1: Instalar dependencias

```powershell
cd "c:\Users\yoeli\Documents\Chefalitas\agent_local"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Paso 2: Registrar scripts Win32 (pywin32)

```powershell
python %LOCALAPPDATA%\Programs\Python\Python3*\Scripts\pywin32_postinstall.py -install
```

Alternativa (buscar el script y ejecutarlo):

```powershell
python - <<'PY'
import site, os, sys
for p in site.getsitepackages():
    cand = os.path.join(p, 'win32', 'Scripts', 'pywin32_postinstall.py')
    if os.path.exists(cand):
        os.execv(sys.executable, [sys.executable, cand, '-install'])
raise SystemExit('pywin32_postinstall.py no encontrado')
PY
```

### Paso 3: Ejecutar GUI de instalación

```powershell
python LocalPrinterAgent.py
```

La GUI permite:
- Instalar dependencias
- Instalar/Actualizar servicio (pywin32)
- Abrir puerto en Firewall
- Iniciar/Detener/Reiniciar servicio
- Abrir logs

## Configuración

### Host y puerto

- Host por defecto: `127.0.0.1`
- Puerto por defecto: `9060`

Cambiar a `0.0.0.0` solo si realmente necesitas acceso desde otra máquina (menos seguro).

### Firewall

En la GUI pulsa “Abrir puerto (Firewall)” o manualmente:

```powershell
netsh advfirewall firewall add rule name="LocalPrinterAgent" dir=in action=allow protocol=TCP localport=9060
```

## Flujo de uso

1) Abre PowerShell como Administrador y ejecuta la GUI.
2) En la GUI:
   - “Instalar dependencias” (si es la primera vez)
   - “Instalar/Actualizar servicio” (pywin32 verbs)
   - “Abrir puerto (Firewall)”
   - “Iniciar”

Alternativas para iniciar el servicio:
- `services.msc` → buscar “LocalPrinterAgent” → Iniciar
- PowerShell (como admin): `python LocalPrinterAgent.py start`

## Monitoreo

### Ver estado

PowerShell (admin):

```powershell
sc query LocalPrinterAgent
```

### Logs

- `agent_local/agent.log` (actividad del agente)
- `agent_local/agent_gui.log` (interacciones GUI)

## Conexión desde Odoo/POS (HTTP sin SSL)

El agente expone endpoints HTTP locales:

- GET `http://127.0.0.1:9060/health` → `{ "status": "ok", "version": "x.y.z" }`
- GET `http://127.0.0.1:9060/printers` → `{ "status": "ok", "printers": [...] }`
- POST `http://127.0.0.1:9060/print` con JSON: `{ "type": "raw|pdf|image", "printer": "Nombre", "data": "<base64>" }`

Autenticación opcional vía `Authorization: Bearer <token>`.

## Solución de problemas

### StartService FAILED 1053

Normalmente indica que pywin32 no quedó registrado correctamente.

```powershell
python -m pip uninstall -y pywin32
python -m pip install pywin32
python <ruta-a>/pywin32_postinstall.py -install
```

Reinstala el servicio desde la GUI y vuelve a iniciar.

### Puerto 9060 en uso

Cambiar el puerto en la GUI antes de instalar el servicio o identificar el proceso:

```powershell
netstat -ano | findstr :9060
taskkill /PID <PID> /F
```

### El servicio no inicia

Revisa `agent_local/agent.log` y el Visor de eventos (Application). Problemas comunes:
- Port busy
- Module not found (falta dependencia)
- Permission denied (ejecutar como admin)

## Empaquetado (opcional)

Usar PyInstaller:

```powershell
pyinstaller --onefile --windowed --name LocalPrinterAgent agent_local/LocalPrinterAgent.py
```

Copiar `dist/LocalPrinterAgent.exe` a `addons/pos_any_printer_local/static/download/` para exponerlo desde Odoo.

