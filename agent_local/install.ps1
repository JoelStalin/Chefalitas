# LocalPrinterAgent Quick Install Script (PowerShell)
# Requires Administrator privileges
# Usage: Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process; .\install.ps1

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

Write-Host "`n========================================================" -ForegroundColor Cyan
Write-Host "LocalPrinterAgent - Instalación Rápida (PowerShell)" -ForegroundColor Cyan
Write-Host "========================================================`n" -ForegroundColor Cyan

# Verify running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: Se requieren permisos de Administrador." -ForegroundColor Red
    Write-Host "`nPor favor, ejecuta PowerShell como Administrador:`n" -ForegroundColor Yellow
    Write-Host "  1. Presiona Ctrl + Shift + Esc"
    Write-Host "  2. Busca 'PowerShell'"
    Write-Host "  3. Click derecho → Ejecutar como Administrador"
    Write-Host "  4. Ejecuta: Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process"
    Write-Host "  5. Ejecuta: .\install.ps1`n"
    Read-Host "Presiona Enter para salir"
    exit 1
}

# Get script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Push-Location $scriptDir

try {
    # Step 1: Check Python
    Write-Host "[1/6] Verificando Python..." -ForegroundColor Yellow
    $pythonVersion = & python --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Python no está instalado o no está en PATH"
    }
    Write-Host "OK: $pythonVersion`n" -ForegroundColor Green

    # Step 2: Upgrade pip
    Write-Host "[2/6] Actualizando pip..." -ForegroundColor Yellow
    & python -m pip install --upgrade pip 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARNING: Error al actualizar pip, continuando...`n" -ForegroundColor Yellow
    } else {
        Write-Host "OK: pip actualizado`n" -ForegroundColor Green
    }

    # Step 3: Install dependencies
    Write-Host "[3/6] Instalando dependencias (requirements.txt)..." -ForegroundColor Yellow
    & python -m pip install --upgrade -r requirements.txt 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudieron instalar dependencias"
    }
    Write-Host "OK: Dependencias instaladas`n" -ForegroundColor Green

    # Step 4: Register Win32 services
    Write-Host "[4/6] Registrando servicios Win32..." -ForegroundColor Yellow
    $pywinPath = & python -c "import site, os; print(os.path.join(site.getsitepackages()[0], 'win32', 'Scripts', 'pywin32_postinstall.py'))" 2>&1
    if (Test-Path $pywinPath) {
        & python "$pywinPath" -install 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "OK: Scripts Win32 registrados`n" -ForegroundColor Green
        } else {
            Write-Host "WARNING: Error al registrar scripts Win32 (opcional)`n" -ForegroundColor Yellow
        }
    } else {
        Write-Host "WARNING: Script postinstall no encontrado (opcional)`n" -ForegroundColor Yellow
    }

    # Step 5: Optional OpenSSL download (for HTTPS mode)
    Write-Host "[5/6] Instalando/verificando OpenSSL (opcional para HTTPS)..." -ForegroundColor Yellow
    try {
        python - <<'PY'
from LocalPrinterAgent import download_and_install_openssl, configure_agent_logging, safe_app_dir
import logging
logger = configure_agent_logging(safe_app_dir())
download_and_install_openssl()
PY
    } catch { }

    # Step 6: Launch GUI
    Write-Host "[6/6] Abriendo GUI de instalación..." -ForegroundColor Yellow
    Write-Host "`nEn la ventana GUI:" -ForegroundColor Cyan
    Write-Host "  1) Instalar/Actualizar servicio" -ForegroundColor Cyan
    Write-Host "  2) Abrir puerto (Firewall)" -ForegroundColor Cyan
    Write-Host "  3) Iniciar" -ForegroundColor Cyan
    Write-Host "`nPresiona cualquier tecla para continuar..." -ForegroundColor Yellow
    $null = Read-Host

    & python LocalPrinterAgent.py

    Write-Host "`nInstalación completada.`n" -ForegroundColor Green

} catch {
    Write-Host "ERROR: $_" -ForegroundColor Red
    Write-Host "`nPresiona Enter para salir..." -ForegroundColor Yellow
    Read-Host | Out-Null
    exit 1
} finally {
    Pop-Location
}

