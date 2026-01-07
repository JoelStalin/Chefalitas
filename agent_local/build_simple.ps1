# Script para generar setup.exe de LocalPrinterAgent
# Corregido: sin emojis, sin caracteres especiales

param(
    [switch]$Clean,
    [string]$InnoSetupPath = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)

$ErrorActionPreference = "Stop"

# Cambiar al directorio del script
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

Write-Host "[INFO] === Build de LocalPrinterAgent Setup.exe ===" -ForegroundColor Cyan
Write-Host "[INFO] Directorio: $(Get-Location)" -ForegroundColor Cyan

# Verificar que estamos en la carpeta correcta
if (-not (Test-Path "LocalPrinterAgent.py")) {
    Write-Host "[ERROR] LocalPrinterAgent.py no encontrado" -ForegroundColor Red
    exit 1
}

# Verificar Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[OK] Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python no encontrado" -ForegroundColor Red
    exit 1
}

# Verificar PyInstaller
try {
    $pyinstallerVersion = pyinstaller --version 2>&1
    Write-Host "[OK] PyInstaller: $pyinstallerVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] PyInstaller no instalado. Ejecuta: pip install pyinstaller" -ForegroundColor Red
    exit 1
}

# Verificar Inno Setup
if (-not (Test-Path $InnoSetupPath)) {
    Write-Host "[WARN] Inno Setup no encontrado. Buscando..." -ForegroundColor Yellow
    $altPaths = @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files (x86)\Inno Setup\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    )
    $found = $false
    foreach ($path in $altPaths) {
        if (Test-Path $path) {
            $InnoSetupPath = $path
            Write-Host "[OK] Inno Setup encontrado en: $path" -ForegroundColor Green
            $found = $true
            break
        }
    }
    if (-not $found) {
        Write-Host "[ERROR] Inno Setup no encontrado. Descargalo desde: https://jrsoftware.org/isdl.php" -ForegroundColor Red
        exit 1
    }
}

# Limpiar builds anteriores si se especifica
if ($Clean) {
    Write-Host "[INFO] Limpiando builds anteriores..." -ForegroundColor Cyan
    Remove-Item -Path build, dist, LocalPrinterAgent.spec -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] Limpieza completada" -ForegroundColor Green
}

# Generar ejecutable con PyInstaller
Write-Host "[INFO] Generando ejecutable con PyInstaller..." -ForegroundColor Cyan

$pyinstallerCmd = @(
    "--noconfirm",
    "--onefile",
    "--windowed",
    "--icon=LocalPrinterAgent.ico",
    "--name=LocalPrinterAgent",
    "--hidden-import=win32print",
    "--hidden-import=win32api",
    "--hidden-import=win32serviceutil",
    "--hidden-import=win32service",
    "--hidden-import=win32event",
    "--hidden-import=servicemanager",
    "LocalPrinterAgent.py"
)

try {
    & pyinstaller @pyinstallerCmd
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] PyInstaller fallo" -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] Ejecutable generado: dist\LocalPrinterAgent.exe" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Error con PyInstaller: $_" -ForegroundColor Red
    exit 1
}

# Verificar que el ejecutable fue creado
if (-not (Test-Path "dist\LocalPrinterAgent.exe")) {
    Write-Host "[ERROR] dist\LocalPrinterAgent.exe no fue generado" -ForegroundColor Red
    exit 1
}

$exeSize = (Get-Item "dist\LocalPrinterAgent.exe").Length / 1MB
Write-Host "[OK] Tamaño: $([math]::Round($exeSize, 2)) MB" -ForegroundColor Green

# Compilar setup.exe con Inno Setup
Write-Host "[INFO] Compilando setup.exe con Inno Setup..." -ForegroundColor Cyan
Write-Host "[INFO] ISCC.exe: $InnoSetupPath" -ForegroundColor Cyan

try {
    & $InnoSetupPath "installer.iss"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Inno Setup fallo" -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] Setup compilado exitosamente" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Error con Inno Setup: $_" -ForegroundColor Red
    exit 1
}

# Verificar resultado final
if (-not (Test-Path "dist\LocalPrinterAgent-Setup.exe")) {
    Write-Host "[ERROR] dist\LocalPrinterAgent-Setup.exe no fue generado" -ForegroundColor Red
    exit 1
}

$setupSize = (Get-Item "dist\LocalPrinterAgent-Setup.exe").Length / 1MB
Write-Host "[OK] Instalador: dist\LocalPrinterAgent-Setup.exe (tamaño: $([math]::Round($setupSize, 2)) MB)" -ForegroundColor Green

# Resultado final
Write-Host ""
Write-Host "=== COMPILACION COMPLETADA CON EXITO ===" -ForegroundColor Green
Write-Host ""
Write-Host "Archivos generados:" -ForegroundColor Cyan
Write-Host "  - Ejecutable:   dist\LocalPrinterAgent.exe" -ForegroundColor White
Write-Host "  - Instalador:   dist\LocalPrinterAgent-Setup.exe" -ForegroundColor White
Write-Host ""
Write-Host "Pasos siguientes:" -ForegroundColor Cyan
Write-Host "  1. Ejecuta: .\dist\LocalPrinterAgent-Setup.exe" -ForegroundColor White
Write-Host "  2. Windows debe mostrar dialogo UAC pidiendo admin" -ForegroundColor White
Write-Host "  3. Distribuye dist\LocalPrinterAgent-Setup.exe a usuarios" -ForegroundColor White
Write-Host ""

exit 0
