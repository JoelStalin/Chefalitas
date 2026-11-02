@echo off
schtasks /Delete /F /TN "AnyPrinter" >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*AnyPrinter.ps1*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo AnyPrinter desinstalado.
pause
