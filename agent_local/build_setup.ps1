#!/usr/bin/env powershell
<#
.SYNOPSIS
    Script automatico para generar setup.exe de LocalPrinterAgent con admin obligatorio

.DESCRIPTION
    Este script:
    1. Limpia builds anteriores (opcional)
    2. Genera ejecutable con PyInstaller
    3. Compila setup.exe con Inno Setup
    4. Verifica que todo este correcto

.PARAMETER Clean
    Si se especifica, elimina carpetas build/ y dist/ antes de compilar

.EXAMPLE
    .\build_setup.ps1 -Clean
    .\build_setup.ps1
#>

param(
    [switch]$Clean,
    [string]$InnoSetupPath = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)

$ErrorActionPreference = "Stop"
$WarningPreference = "SilentlyContinue"

# Funciones simples sin emojis
function Write-Info {
    Write-Host "[INFO] $args" -ForegroundColor Cyan
}

function Write-Success {
    Write-Host "[OK] $args" -ForegroundColor Green
}

function Write-Error-Custom {
    Write-Host "[ERROR] $args" -ForegroundColor Red
}

function Write-Warn {
    Write-Host "[WARN] $args" -ForegroundColor Yellow
}

# Verificar que estamos en la carpeta correcta
if (-not (Test-Path "LocalPrinterAgent.py")) {
    Write-Error-Custom "LocalPrinterAgent.py no encontrado. Ejecuta este script desde agent_local/"
    exit 1
}

Write-Info "=== Build de LocalPrinterAgent Setup.exe ==="
Write-Info "Directorio actual: $(Get-Location)"

# === PASO 0: Verificar prerrequisitos ===
Write-Info ""
Write-Info "📋 Verificando prerrequisitos..."

# Verificar Python
try {
    $pythonVersion = python --version 2>&1
    Write-Success "Python: $pythonVersion"
} catch {
    Write-Error-Custom "Python no encontrado o no accesible"
    exit 1
}

# Verificar PyInstaller
try {
    $pyinstallerVersion = pyinstaller --version 2>&1
    Write-Success "PyInstaller: $pyinstallerVersion"
} catch {
    Write-Error-Custom "PyInstaller no instalado. Ejecuta: pip install pyinstaller"
    exit 1
}

# Verificar Inno Setup
if (-not (Test-Path $InnoSetupPath)) {
    Write-Warn "Inno Setup no encontrado en: $InnoSetupPath"
    Write-Info "Buscando Inno Setup en rutas alternativas..."
    
    $altPaths = @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files (x86)\Inno Setup\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    )
    
    $found = $false
    foreach ($path in $altPaths) {
        if (Test-Path $path) {
            $InnoSetupPath = $path
            Write-Success "Inno Setup encontrado en: $path"
            $found = $true
            break
        }
    }
    
    if (-not $found) {
        Write-Error-Custom "Inno Setup no encontrado. Descargalo desde: https://jrsoftware.org/isdl.php"
        exit 1
    }
}

# Verificar archivos necesarios
$requiredFiles = @(
    "LocalPrinterAgent.py",
    "LocalPrinterAgent.ico",
    "installer.iss",
    "README_INSTALLATION.md",
    "LICENSE.txt"
)

Write-Info ""
Write-Info "Verificando archivos necesarios..."
foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Success "$file"
    } else {
        Write-Warn "$file - NO ENCONTRADO"
        if ($file -eq "LICENSE.txt") {
            Write-Info "   Creando LICENSE.txt vacio..."
            @"
LocalPrinterAgent - Proxy HTTP/HTTPS para Impresoras Locales
Version 1.0.0

Copyright (c) 2025 Chefalitas
"@ | Out-File -FilePath LICENSE.txt -Encoding UTF8
            Write-Success "LICENSE.txt creado"
        }
    }
}

# === PASO 1: Limpiar (si se especifica) ===
if ($Clean) {
    Write-Info ""
    Write-Info "🧹 Limpiando builds anteriores..."
    
    $itemsToRemove = @("build", "dist", "LocalPrinterAgent.spec")
    foreach ($item in $itemsToRemove) {
        if (Test-Path $item) {
            Remove-Item -Path $item -Recurse -Force -ErrorAction SilentlyContinue
            Write-Success "Eliminado: $item"
        }
    }
}

# === PASO 2: Generar ejecutable con PyInstaller ===
Write-Info ""
Write-Info "Generando ejecutable con PyInstaller..."

$pyinstallerCmd = @(
    "--noconfirm",
    "--onefile",
    "--windowed",
    "--icon=LocalPrinterAgent.ico",
    "--name=LocalPrinterAgent",
    "--add-data=service_config.json:.",
    "--add-data=README.md:.",
    "--hidden-import=win32print",
    "--hidden-import=win32api",
    "--hidden-import=win32serviceutil",
    "--hidden-import=win32service",
    "--hidden-import=win32event",
    "--hidden-import=servicemanager",
    "LocalPrinterAgent.py"
)

try {
    Write-Info "Ejecutando: pyinstaller $($pyinstallerCmd -join ' ')"
    & pyinstaller @pyinstallerCmd
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error-Custom "PyInstaller falló con código de salida: $LASTEXITCODE"
        exit 1
    }
    
    Write-Success "Ejecutable generado: dist\LocalPrinterAgent.exe"
} catch {
    Write-Error-Custom "Error al ejecutar PyInstaller: $_"
    exit 1
}

# === PASO 3: Verificar ejecutable ===
Write-Info ""
Write-Info "Verificando ejecutable..."

if (-not (Test-Path "dist\LocalPrinterAgent.exe")) {
    Write-Error-Custom "dist\LocalPrinterAgent.exe no fue generado"
    exit 1
}

$exeSize = (Get-Item "dist\LocalPrinterAgent.exe").Length / 1MB
Write-Success "dist\LocalPrinterAgent.exe (tamaño: $([math]::Round($exeSize, 2)) MB)"

# === PASO 4: Compilar setup.exe con Inno Setup ===
Write-Info ""
Write-Info "Compilando setup.exe con Inno Setup..."
Write-Info "ISCC.exe: $InnoSetupPath"

try {
    Write-Info "Ejecutando: $InnoSetupPath installer.iss"
    & $InnoSetupPath "installer.iss"
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error-Custom "Inno Setup fallo con codigo: $LASTEXITCODE"
        exit 1
    }
    
    Write-Success "Setup compilado exitosamente"
} catch {
    Write-Error-Custom "Error al ejecutar Inno Setup: $_"
    exit 1
}

# === PASO 5: Verificar resultado ===
Write-Info ""
Write-Info "Verificando resultado final..."

if (-not (Test-Path "dist\LocalPrinterAgent-Setup.exe")) {
    Write-Error-Custom "dist\LocalPrinterAgent-Setup.exe no fue generado"
    exit 1
}

$setupSize = (Get-Item "dist\LocalPrinterAgent-Setup.exe").Length / 1MB
Write-Success "dist\LocalPrinterAgent-Setup.exe (tamaño: $([math]::Round($setupSize, 2)) MB)"

# === RESULTADO FINAL ===
Write-Info ""
Write-Success "=== COMPILACION COMPLETADA CON EXITO ==="
Write-Info ""
Write-Host "Archivos generados:" -ForegroundColor Cyan
Write-Host "   - Ejecutable:  dist\LocalPrinterAgent.exe" -ForegroundColor White
Write-Host "   - Instalador:  dist\LocalPrinterAgent-Setup.exe" -ForegroundColor White
Write-Host ""
Write-Host "Proximos pasos:" -ForegroundColor Cyan
Write-Host "   1. Prueba el instalador: .\dist\LocalPrinterAgent-Setup.exe" -ForegroundColor White
Write-Host "   2. Windows debe mostrar dialogo UAC (pedira admin)" -ForegroundColor White
Write-Host "   3. Si no pide admin, revisa que el archivo installer.iss sea correcto" -ForegroundColor White
Write-Host ""
Write-Host "Para distribuir:" -ForegroundColor Cyan
Write-Host "   - Sube .\dist\LocalPrinterAgent-Setup.exe a tu servidor" -ForegroundColor White
Write-Host "   - Los usuarios pueden ejecutarlo directamente desde el navegador" -ForegroundColor White
Write-Host ""

# Ofrecer abrir el archivo explorer en la carpeta dist
$openDist = Read-Host "Abrir carpeta dist en explorer? (s/n)"
if ($openDist -eq "s" -or $openDist -eq "S") {
    explorer .\dist
}

exit 0
