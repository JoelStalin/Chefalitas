@echo off
setlocal
cd /d "%~dp0"

echo Detener/Eliminar servicio LocalPrinterAgent...
python LocalPrinterAgent.py stop
python LocalPrinterAgent.py remove

echo Listo.

