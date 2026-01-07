@echo off
setlocal
cd /d "%~dp0"

echo Instalar/Actualizar servicio LocalPrinterAgent...
python LocalPrinterAgent.py install --host 127.0.0.1 --port 9060
if %errorlevel% neq 0 (
  echo Intentando update...
  python LocalPrinterAgent.py update --host 127.0.0.1 --port 9060
)
python LocalPrinterAgent.py start

echo Listo.

