# Guía Completa: Crear setup.exe para LocalPrinterAgent (Admin Obligatorio)

## 📋 Resumen

Este documento detalla cómo crear un **setup.exe profesional** que:
- Requiere **Administrador obligatorio** al iniciar
- Instala LocalPrinterAgent en `Program Files`
- Configura accesos directos en el menú Inicio
- Incluye desinstalador automático
- Soporta idiomas (Español/Inglés)

---

## 🔧 Requisitos previos

### 1. Python y PyInstaller
```powershell
python --version  # Debe ser 3.10+
pip install pyinstaller
```

### 2. Inno Setup (IMPORTANTE)
- Descargar desde: https://jrsoftware.org/isdl.php
- Versión recomendada: **Inno Setup 6.3.0** o superior
- Durante instalación, marcar **"Install Inno Setup Preprocessor"**

### 3. Archivos necesarios
```
agent_local/
├── LocalPrinterAgent.py          (script principal)
├── LocalPrinterAgent.ico          (icono 256x256)
├── installer.iss                  (script de Inno Setup)
├── README_INSTALLATION.md         (instrucciones de instalación)
├── LICENSE.txt                    (licencia - crear si no existe)
├── service_config.json            (configuración de servicio)
└── assets/
    └── LocalPrinterAgent.ico      (icono para assets)
```

---

## 📦 Paso 1: Generar ejecutable con PyInstaller

### Opción A: Build Completo (Recomendado)

```powershell
# Cambiar al directorio agent_local
cd C:\Users\yoeli\Documents\Chefalitas\agent_local

# Limpiar builds anteriores
Remove-Item -Path build, dist -Recurse -Force -ErrorAction SilentlyContinue

# Generar ejecutable con soporte completo
pyinstaller --noconfirm `
  --onefile `
  --windowed `
  --icon=LocalPrinterAgent.ico `
  --name=LocalPrinterAgent `
  --add-data="service_config.json:." `
  --add-data="README.md:." `
  --hidden-import=win32print `
  --hidden-import=win32api `
  --hidden-import=win32serviceutil `
  --hidden-import=win32service `
  --hidden-import=win32event `
  --hidden-import=servicemanager `
  LocalPrinterAgent.py
```

### Opción B: Build con Console (Para Debugging)

```powershell
pyinstaller --noconfirm `
  --onefile `
  --console `
  --icon=LocalPrinterAgent.ico `
  --name=LocalPrinterAgent `
  --add-data="service_config.json:." `
  --hidden-import=win32print `
  LocalPrinterAgent.py
```

**Salida esperada:**
```
dist/
├── LocalPrinterAgent.exe     ← El ejecutable final
build/                         ← Archivos temporales
LocalPrinterAgent.spec        ← Especificación (NO EDITAR)
```

---

## 🛠️ Paso 2: Preparar archivos para el instalador

### 2.1 Crear archivo LICENSE.txt

```powershell
@"
LocalPrinterAgent - Proxy HTTP/HTTPS para Impresoras Locales
Versión 1.0.0

Copyright (c) 2025 Chefalitas

Permiso otorgado para usar, modificar y distribuir este software.
"@ | Out-File -FilePath LICENSE.txt -Encoding UTF8
```

### 2.2 Verificar archivos necesarios

```powershell
# Verificar que existan:
Test-Path .\dist\LocalPrinterAgent.exe           # Debe ser TRUE
Test-Path .\LocalPrinterAgent.ico                # Debe ser TRUE
Test-Path .\installer.iss                        # Debe ser TRUE
Test-Path .\README_INSTALLATION.md               # Debe ser TRUE
Test-Path .\LICENSE.txt                          # Debe ser TRUE
```

---

## 🏗️ Paso 3: Compilar setup.exe con Inno Setup

### Opción A: Desde línea de comandos (Recomendado)

```powershell
# Ruta típica de Inno Setup en Windows
$inno = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

# Compilar el instalador
& $inno "installer.iss"
```

**Salida esperada:**
```
dist/
└── LocalPrinterAgent-Setup.exe  ← SETUP LISTO PARA DISTRIBUIR
```

### Opción B: Desde la GUI de Inno Setup

1. Abrir **Inno Setup Compiler**
2. File → Open
3. Seleccionar `installer.iss`
4. Build → Compile
5. El archivo `LocalPrinterAgent-Setup.exe` se genera en `dist/`

### Opción C: Script PowerShell automático

Crear archivo `build_setup.ps1`:

```powershell
param([switch]$Clean)

$ErrorActionPreference = "Stop"

# Rutas
$agentDir = Split-Path -Parent $PSScriptRoot
$innoSetup = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

if (-not (Test-Path $innoSetup)) {
    Write-Host "❌ Inno Setup no encontrado en: $innoSetup" -ForegroundColor Red
    exit 1
}

if ($Clean) {
    Write-Host "🧹 Limpiando builds anteriores..."
    Remove-Item -Path build, dist -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "📦 Generando ejecutable con PyInstaller..." -ForegroundColor Cyan
pyinstaller --noconfirm `
  --onefile `
  --windowed `
  --icon=LocalPrinterAgent.ico `
  --name=LocalPrinterAgent `
  --hidden-import=win32print `
  LocalPrinterAgent.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ PyInstaller falló" -ForegroundColor Red
    exit 1
}

Write-Host "🛠️  Compilando setup.exe con Inno Setup..." -ForegroundColor Cyan
& $innoSetup "installer.iss"

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Setup.exe generado exitosamente en: dist\LocalPrinterAgent-Setup.exe" -ForegroundColor Green
} else {
    Write-Host "❌ Inno Setup falló" -ForegroundColor Red
    exit 1
}
```

Ejecutar:
```powershell
.\build_setup.ps1 -Clean
```

---

## ✅ Paso 4: Verificar que setup.exe requiere ADMIN

### Test 1: Verificar permisos en propiedades

```powershell
# Click derecho en dist\LocalPrinterAgent-Setup.exe → Propiedades → Compatibilidad
# Debe estar marcado: "Ejecutar este programa como administrador"
```

### Test 2: Ejecutar setup.exe

```powershell
# Abrir PowerShell NO elevado
cd C:\Users\yoeli\Documents\Chefalitas\agent_local\dist
.\LocalPrinterAgent-Setup.exe

# Windows DEBE mostrar diálogo UAC pidiendo permisos
# Esto es lo primero que aparece (ANTES del wizard)
```

### Test 3: Verificar instalación

```powershell
# Tras hacer clic "Instalar":
# Archivos deben estar en:
Test-Path "C:\Program Files\LocalPrinterAgent\LocalPrinterAgent.exe"
Test-Path "C:\Program Files\LocalPrinterAgent\LocalPrinterAgent.ico"

# Acceso directo en menú inicio:
Test-Path "$env:PROGRAMDATA\Microsoft\Windows\Start Menu\Programs\LocalPrinterAgent"
```

---

## 🔒 Cómo setup.exe garantiza ADMIN obligatorio

El archivo `installer.iss` contiene estas líneas clave:

```ini
[Setup]
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=no
```

**Que significa:**
- `PrivilegesRequired=admin` → Fuerza admin obligatorio
- `PrivilegesRequiredOverridesAllowed=no` → El usuario NO puede saltarse esto

**Flujo de ejecución:**

```
Usuario hace doble clic en setup.exe
    ↓
Windows detecta PrivilegesRequired=admin
    ↓
Muestra diálogo UAC pidiendo "¿Permitir cambios?"
    ↓
Si hace clic "Sí" → Abre wizard de instalación con admin
    ↓
Si hace clic "No" → Setup.exe se cierra sin instalar
```

---

## 📝 Contenido de installer.iss

El archivo `installer.iss` YA existe en tu carpeta. Contiene:

✅ Admin obligatorio (`PrivilegesRequired=admin`)
✅ Interfaz moderna (WizardStyle=modern)
✅ Idiomas español/inglés
✅ Componentes opcionales (servicio, acceso directo)
✅ Desinstalador automático
✅ Icono personalizado

---

## 🚀 Flujo COMPLETO (paso a paso)

### Terminal PowerShell (como usuario normal, NO admin):

```powershell
# 1. Ir a la carpeta
cd C:\Users\yoeli\Documents\Chefalitas\agent_local

# 2. Verificar que todo esté listo
ls LocalPrinterAgent.py
ls LocalPrinterAgent.ico
ls installer.iss
ls README_INSTALLATION.md
ls LICENSE.txt

# 3. Generar ejecutable
pyinstaller --noconfirm --onefile --windowed --icon=LocalPrinterAgent.ico `
  --name=LocalPrinterAgent LocalPrinterAgent.py

# 4. Compilar setup.exe
$inno = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
& $inno "installer.iss"

# 5. Verificar resultado
ls dist\LocalPrinterAgent-Setup.exe
```

### Resultado:
```
✅ dist\LocalPrinterAgent-Setup.exe  (archivo listo para distribuir)
```

---

## 🐛 Troubleshooting

### ❌ "Inno Setup no encontrado"

```powershell
# Verificar ruta de instalación:
ls "C:\Program Files (x86)\Inno Setup 6\"

# Si está en otra ruta:
$inno = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"  # Ajustar aquí
```

### ❌ "PyInstaller: Module not found"

```powershell
# Instalar módulos faltantes
pip install pywin32 pillow PyPDF2 requests

# Regenerar exe
pyinstaller --noconfirm --onefile --windowed LocalPrinterAgent.py
```

### ❌ "Setup.exe no pide admin"

```powershell
# Verificar installer.iss contiene:
Select-String -Path installer.iss -Pattern "PrivilegesRequired=admin"
# Debe mostrar la línea

# Recompilar:
& $inno "installer.iss"
```

### ❌ "Errores de ISCC.exe"

```powershell
# Ejecutar ISCC con ruta completa y sin captura:
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" "C:\Users\yoeli\Documents\Chefalitas\agent_local\installer.iss"
```

---

## 📤 Distribución

### Archivo final para usuarios:
```
dist/LocalPrinterAgent-Setup.exe     (~ 50-100 MB)
```

### Instrucciones para usuarios:

1. Descargar `LocalPrinterAgent-Setup.exe`
2. Hacer doble clic
3. Aceptar diálogo UAC de Windows
4. Seguir wizard de instalación
5. Hacer clic "Instalar"
6. Al terminar, LocalPrinterAgent se abrirá automáticamente

---

## 🔄 Actualización (Versiones futuras)

Para generar una nueva versión:

```powershell
# 1. Actualizar versión en installer.iss:
# Línea: AppVersion=1.0.1

# 2. Regenerar
pyinstaller --noconfirm --onefile --windowed LocalPrinterAgent.py
$inno = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
& $inno "installer.iss"

# 3. Nuevo archivo de setup se genera:
# dist/LocalPrinterAgent-Setup.exe
```

---

## 📌 Resumen de Comandos

```powershell
# Limpiar
Remove-Item -Path build, dist -Recurse -Force -ErrorAction SilentlyContinue

# Build EXE
pyinstaller --noconfirm --onefile --windowed --icon=LocalPrinterAgent.ico `
  --name=LocalPrinterAgent LocalPrinterAgent.py

# Build Setup.exe
$inno = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
& $inno "installer.iss"

# Resultado
ls dist\LocalPrinterAgent-Setup.exe
```

---

**✅ Done: Ahora tienes un setup.exe profesional con admin obligatorio.**

