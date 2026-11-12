@echo off
rem Abre la gaveta usando AnyPrinter (la impresora configurada o la predeterminada).
powershell -NoProfile -ExecutionPolicy Bypass -Command "$c=Get-Content '%~dp0config.json' -Raw|ConvertFrom-Json; try { $r=Invoke-RestMethod -Method Post -Uri ('http://127.0.0.1:'+$c.port+'/open-drawer') -Headers @{'X-Printer-Token'=$c.token} -Body '{}' -ContentType 'application/json'; if ($r.ok) { 'Caja abierta' } else { 'No se pudo abrir' } } catch { 'AnyPrinter no esta corriendo. Ejecute instalar.bat'; exit 1 }"
if errorlevel 1 pause
