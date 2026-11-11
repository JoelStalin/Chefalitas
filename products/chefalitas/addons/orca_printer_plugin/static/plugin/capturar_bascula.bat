@echo off
chcp 65001 >nul
echo ============================================
echo   Captura de bascula (para configurar AnyPrinter)
echo ============================================
echo Pon un peso sobre la bascula y dejalo mientras corre (60 segundos).
echo.
echo Escribe la IP y el puerto de la bascula (ejemplo 192.168.1.50:4001)
echo o el puerto serie (ejemplo COM3).
set /p DESTINO=Destino:
if "%DESTINO%"=="" goto fin
echo %DESTINO% | findstr /i "^COM" >nul
if %errorlevel%==0 (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0capturar_bascula.ps1" -Com %DESTINO%
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0capturar_bascula.ps1" -Tcp %DESTINO%
)
echo.
echo Manda el archivo captura_bascula_*.txt que quedo en esta carpeta.
:fin
pause
