# 🚀 INSTRUCCIONES PARA CREAR setup.exe

## ⚡ TL;DR (Versión ultra rápida)

```powershell
# 1. Abre PowerShell en agent_local/
cd C:\Users\yoeli\Documents\Chefalitas\agent_local

# 2. Ejecuta:
.\build_setup.ps1 -Clean

# 3. Espera a que termine
# Resultado: dist\LocalPrinterAgent-Setup.exe
```

---

## 📋 Requisitos (Verificar antes de empezar)

### ✅ 1. Python 3.10+
```powershell
python --version
# Debe mostrar: Python 3.10.x o superior
```

### ✅ 2. PyInstaller
```powershell
pyinstaller --version
# Si NO está instalado:
pip install pyinstaller
```

### ✅ 3. Inno Setup 6.3+
- Descargar desde: https://jrsoftware.org/isdl.php
- Instalador típico: `jsetup-6.3.0.exe`
- Marcar "Install Inno Setup Preprocessor" durante instalación
- Ubicación predeterminada: `C:\Program Files (x86)\Inno Setup 6\`

### ✅ 4. Archivos en agent_local/
```powershell
# Ejecutar esto para verificar:
ls LocalPrinterAgent.py
ls LocalPrinterAgent.ico
ls installer.iss
ls README_INSTALLATION.md
ls LICENSE.txt
ls service_config.json
```

---

## 🎬 OPCIÓN A: Automático (RECOMENDADO - 2 minutos)

### Paso 1: Abrir PowerShell

Windows + R → `powershell` → Enter

```powershell
cd C:\Users\yoeli\Documents\Chefalitas\agent_local
```

### Paso 2: Ejecutar script
```powershell
# Dar permisos de ejecución (solo primera vez)
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force

# Ejecutar build
.\build_setup.ps1 -Clean
```

### Paso 3: Esperar
El script:
- Verifica requisitos ✅
- Genera EXE con PyInstaller (~30 segundos)
- Compila setup.exe con Inno Setup (~10 segundos)
- Muestra resultado final

### Paso 4: Resultado
```
✅ === ¡COMPILACIÓN COMPLETADA CON ÉXITO! ===
📁 Archivos generados:
   • Ejecutable:  dist\LocalPrinterAgent.exe
   • Instalador:  dist\LocalPrinterAgent-Setup.exe
```

---

## 🛠️ OPCIÓN B: Manual (Si el script falla)

### Paso 1: Limpiar builds anteriores
```powershell
cd C:\Users\yoeli\Documents\Chefalitas\agent_local

# Eliminar carpetas de compilaciones previas
Remove-Item -Path build, dist -Recurse -Force -ErrorAction SilentlyContinue
```

### Paso 2: Generar ejecutable
```powershell
pyinstaller --noconfirm `
  --onefile `
  --windowed `
  --icon=LocalPrinterAgent.ico `
  --name=LocalPrinterAgent `
  --hidden-import=win32print `
  --hidden-import=win32api `
  --hidden-import=win32serviceutil `
  LocalPrinterAgent.py
```

**Esperar hasta que aparezca:**
```
Successfully built ...
Executable: C:\Users\yoeli\Documents\Chefalitas\agent_local\dist\LocalPrinterAgent.exe
```

### Paso 3: Compilar setup.exe
```powershell
# Verificar ruta de Inno Setup
$inno = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

# Si no existe, buscar en ruta alternativa:
# $inno = "C:\Program Files (x86)\Inno Setup\ISCC.exe"

# Compilar
& $inno "installer.iss"
```

**Esperar hasta que aparezca:**
```
Inno Setup Compiler Verbose Output
...
Done.
```

### Paso 4: Verificar resultado
```powershell
ls dist\LocalPrinterAgent-Setup.exe
# Debe mostrar el archivo (~ 50-100 MB)
```

---

## ✔️ VERIFICAR QUE REQUIERE ADMIN

### Test 1: Ejecutar setup.exe
```powershell
.\dist\LocalPrinterAgent-Setup.exe
```

**Debe aparecer INMEDIATAMENTE:**
```
┌─────────────────────────────────────┐
│ Control de Cuentas de Usuario       │
│                                     │
│ ¿Deseas permitir que esta aplicación│
│ realice cambios en tu dispositivo?  │
│                                     │
│           [No]   [Sí]              │
└─────────────────────────────────────┘
```

**Si NO aparece este diálogo:**
- El archivo `installer.iss` puede estar mal
- O Inno Setup no lo compiló correctamente
- Verificar que contenga: `PrivilegesRequired=admin`

### Test 2: Hacer clic "Sí"
Debe abrir el wizard de instalación:
```
LocalPrinterAgent Setup
┌──────────────────────────────────┐
│ Welcome                          │
│ Please select installation type: │
│ ○ Complete                       │
│ ○ Compact                        │
│ ○ Custom                         │
│                                  │
│ [Next >]                         │
└──────────────────────────────────┘
```

### Test 3: Hacer clic "No" en UAC
setup.exe se cierra sin hacer nada. ✅ **Correcto** (admin era obligatorio).

---

## 📦 RESULTADO FINAL

```
Archivo:  dist\LocalPrinterAgent-Setup.exe
Tamaño:   ~ 50-100 MB
Estado:   ✅ Listo para distribuir
```

### Distribuir a usuarios:
1. Descargar `dist\LocalPrinterAgent-Setup.exe`
2. Hacer doble clic
3. Windows pide admin (✅ lo primero que ve)
4. Seguir wizard
5. ¡Listo!

---

## 🐛 TROUBLESHOOTING

### ❌ "El archivo build_setup.ps1 no puede ejecutarse"

```powershell
# Permitir ejecución temporal
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force
.\build_setup.ps1 -Clean

# Después se revierte automáticamente
```

### ❌ "PyInstaller no encontrado"

```powershell
pip install pyinstaller
pyinstaller --version
# Debe mostrar un número de versión
```

### ❌ "Inno Setup no encontrado"

```powershell
# Verificar ruta real
ls "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

# Si no existe, buscar:
Get-ChildItem "C:\Program Files*" -Name -Filter "ISCC.exe" -Recurse

# En el script, cambiar la ruta en build_setup.ps1:
$InnoSetupPath = "C:\ruta\real\ISCC.exe"
```

### ❌ "Setup.exe no pide admin"

```powershell
# Verificar que installer.iss contenga:
Select-String -Path installer.iss -Pattern "PrivilegesRequired=admin"

# Debe mostrar:
# PrivilegesRequired=admin

# Si no está, agregar a [Setup]
# Luego recompilar:
$inno = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
& $inno "installer.iss"
```

### ❌ "Error: LocalPrinterAgent.exe no se genera"

```powershell
# Verificar que el script no tiene errores:
python -m py_compile LocalPrinterAgent.py

# Si falta icono:
# Crear uno temporal o comentar --icon
pyinstaller --noconfirm --onefile --windowed LocalPrinterAgent.py
```

### ❌ "Antivirus marca setup.exe como malware"

Es normal en archivos generados sin firmar. Soluciones:

```
1. Temporal: Agregar excepción en antivirus
2. Permanente: Firmar digitalmente el .exe (requiere certificado)
3. Usuarios: Descargar desde sitio confiable (HTTPS, SSL válido)
```

---

## 📝 Archivos generados

### Durante compilación:
```
agent_local/
├── build/                      (temporales)
├── dist/
│   ├── LocalPrinterAgent.exe           ← EXE puro
│   └── LocalPrinterAgent-Setup.exe     ← ⭐ SETUP (distribuir)
└── LocalPrinterAgent.spec       (especificación)
```

### Conservar:
```
✅ dist/LocalPrinterAgent-Setup.exe  (archivo de instalación)
```

### Limpiar (opcional):
```
❌ build/   (no necesario después de compilar)
❌ *.spec   (no necesario después de compilar)
```

---

## 🔄 Actualizar versión (futuro)

```powershell
# 1. Editar installer.iss
# Cambiar: AppVersion=1.0.0 → AppVersion=1.0.1

# 2. Recompilar
.\build_setup.ps1 -Clean

# 3. Nuevo setup.exe se genera con nueva versión
```

---

## ✅ CHECKLIST FINAL

Antes de distribuir:

- [ ] `dist\LocalPrinterAgent-Setup.exe` existe
- [ ] Tamaño > 10 MB (< 200 MB es normal)
- [ ] Ejecutar setup.exe muestra UAC
- [ ] UAC pide "Administrador"
- [ ] Wizard de instalación abre tras aceptar UAC
- [ ] Instalación completa sin errores
- [ ] Archivos en `C:\Program Files\LocalPrinterAgent\`
- [ ] App se abre al terminar instalación
- [ ] Acceso directo en menú Inicio

---

## 📞 RESUMEN RÁPIDO

**Para crear setup.exe:**
```powershell
cd C:\Users\yoeli\Documents\Chefalitas\agent_local
.\build_setup.ps1 -Clean
# Esperar 1-2 minutos
# Resultado: dist\LocalPrinterAgent-Setup.exe
```

**Para verificar admin obligatorio:**
```powershell
.\dist\LocalPrinterAgent-Setup.exe
# Windows DEBE mostrar diálogo UAC
```

**Para distribuir:**
```
Envía este archivo a usuarios:
dist\LocalPrinterAgent-Setup.exe
```

---

**✅ ¡LISTO! Tu setup.exe profesional con admin obligatorio está creado.**
