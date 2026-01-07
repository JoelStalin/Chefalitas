@echo off

echo.
echo ========================================================
echo LocalPrinterAgent - Instalación Rápida
echo ========================================================
echo.

REM Check if running as Administrator
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Se requieren permisos de Administrador.
    echo.
    echo Por favor, ejecuta este script como Administrador:
    echo 1. Presiona Win + R
    echo 2. Escribe: cmd
    echo 3. Presiona Ctrl + Shift + Enter
    echo 4. Navega a esta carpeta y ejecuta: install.bat
    echo.
    pause
    exit /b 1
)

setlocal enabledelayedexpansion

cd /d "%~dp0"

echo [1/6] Verificando Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python no está instalado o no está en PATH
    pause
    exit /b 1
)
echo OK: Python encontrado

echo.
echo [2/6] Actualizando pip...
python -m pip install --upgrade pip >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNING: Error al actualizar pip, continuando...
)
echo OK: pip actualizado

echo.
echo [3/6] Instalando dependencias desde requirements.txt...
python -m pip install --upgrade -r requirements.txt >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: No se pudieron instalar dependencias
    pause
    exit /b 1
)
echo OK: Dependencias instaladas

echo.
echo [4/6] Registrando servicios Win32...
python -c "import sys; import os; sys.path.insert(0, os.path.join(sys.prefix, 'Scripts')); exec(open(os.path.join(sys.prefix, 'Scripts', 'pywin32_postinstall.py')).read())" -install >nul 2>&1
REM Esto es un intento suave; si falla, continúa
echo OK: Scripts Win32 registrados (o saltados)

echo.
echo [5/6] Instalando/Verificando OpenSSL...
python -c "from LocalPrinterAgent import download_and_install_openssl, configure_agent_logging, safe_app_dir; import logging; logger = configure_agent_logging(safe_app_dir()); download_and_install_openssl()" >nul 2>&1
echo OK: OpenSSL instalado (o ya estaba disponible)

echo.
echo [6/6] Abriendo GUI...
echo.
python LocalPrinterAgent.py

echo.
echo Instalación completada.
pause
