@echo off
rem Instala AnyPrinter en segundo plano: arranca solo cada vez que se enciende o reinicia la PC.
set "DIR=%~dp0"
set "CMD=powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File \"%DIR%AnyPrinter.ps1\""

rem 1) Con permisos de administrador: arranca con Windows, antes de iniciar sesion.
schtasks /Create /F /SC ONSTART /RU SYSTEM /TN "AnyPrinter" /TR "%CMD%" >nul 2>&1
if not errorlevel 1 (
  echo Modo: arranca con el encendido de la PC.
  goto started
)
rem 2) Sin administrador: arranca al iniciar sesion en Windows.
schtasks /Create /F /SC ONLOGON /TN "AnyPrinter" /TR "%CMD%" /RL LIMITED >nul 2>&1
if errorlevel 1 ( echo No pude crear la tarea de inicio. & pause & exit /b 1 )
echo Modo: arranca al iniciar sesion. Para que arranque antes, ejecute este archivo como administrador.

:started
start "" powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "%DIR%AnyPrinter.ps1"
echo AnyPrinter instalado y funcionando en segundo plano.
echo Se abre la pagina para escoger la impresora de caja y la de cocina.
timeout /t 3 >nul
start "" http://127.0.0.1:9050/
pause
