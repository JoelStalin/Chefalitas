# Cómo preparar el instalable del Agente de Impresión Local

Este directorio aloja el instalador final `LocalPrinterAgent-Setup.exe` que Odoo servirá desde el botón “Descargar agente”.

## Prerrequisitos

1. Python 3 (para construir, no para el usuario final)
2. PyInstaller (`pip install pyinstaller`) – opcional si crea EXE standalone
3. Inno Setup (https://jrsoftware.org/isinfo.php)

## Pasos para la compilación

1) Navegue a `agent_local/` (raíz del repo):
```
cd agent_local
```

2) (Opcional) Construya un EXE standalone:
```
pyinstaller --onefile --windowed --name=LocalPrinterAgent agent_local/LocalPrinterAgent.py
```

3) Compile el instalador con Inno Setup:
- Abra Inno Setup Compiler → File > Open → `agent_local/installer.iss`
- Build > Compile (F9)

El instalador ejecutará scripts para instalar dependencias y registrar pywin32.

4) Copie el archivo generado:
- De `agent_local/Output/LocalPrinterAgent-Setup.exe` (o donde lo genere su Inno) a:
  `addons/pos_any_printer_local/static/download/`
- (Opcional) Copie también `LocalPrinterAgent.exe` como fallback.

