# ⚡ GUÍA RÁPIDA: Crear setup.exe para LocalPrinterAgent

## 🎯 Objetivo
Crear un instalador `setup.exe` que **requiera Administrador obligatorio** al ejecutarse.

---

## ✅ Checklist de Preparación

- [ ] **Python 3.10+** instalado: `python --version`
- [ ] **PyInstaller** instalado: `pip install pyinstaller`
- [ ] **Inno Setup 6.3.0+** descargado desde https://jrsoftware.org/isdl.php
- [ ] Archivos presentes en `agent_local/`:
  - [ ] `LocalPrinterAgent.py`
  - [ ] `LocalPrinterAgent.ico` (256x256 recomendado)
  - [ ] `installer.iss` (ya existe)
  - [ ] `README_INSTALLATION.md`
  - [ ] `LICENSE.txt` (crear si no existe)
  - [ ] `service_config.json`

---

## 🚀 OPCIÓN 1: Usando el script automático (RECOMENDADO)

### Paso 1: Ejecutar script
```powershell
cd C:\Users\yoeli\Documents\Chefalitas\agent_local
.\build_setup.ps1 -Clean
```

**Listo.** El script:
- Verifica todos los requisitos
- Genera ejecutable con PyInstaller
- Compila setup.exe con Inno Setup
- Muestra el resultado

### Resultado esperado:
```
✅ === ¡COMPILACIÓN COMPLETADA CON ÉXITO! ===
📁 Archivos generados:
   • Ejecutable:  dist\LocalPrinterAgent.exe
   • Instalador:  dist\LocalPrinterAgent-Setup.exe
```

---

## 🛠️ OPCIÓN 2: Manual paso a paso

### Paso 1: Generar ejecutable
```powershell
cd C:\Users\yoeli\Documents\Chefalitas\agent_local

pyinstaller --noconfirm `
  --onefile `
  --windowed `
  --icon=LocalPrinterAgent.ico `
  --name=LocalPrinterAgent `
  --hidden-import=win32print `
  LocalPrinterAgent.py
```

✅ Resultado: `dist\LocalPrinterAgent.exe`

### Paso 2: Compilar setup.exe
```powershell
$inno = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
& $inno "installer.iss"
```

✅ Resultado: `dist\LocalPrinterAgent-Setup.exe`

---

## ✔️ Verificar que requiere ADMIN obligatorio

### Test 1: Ejecutar setup.exe
```powershell
.\dist\LocalPrinterAgent-Setup.exe
```

**Windows DEBE mostrar:**
```
┌─────────────────────────────────────┐
│ Deseas permitir que esta aplicación │
│ realice cambios en tu dispositivo?  │
│                                     │
│  [No]  [Sí]                        │
└─────────────────────────────────────┘
```

Si **NO aparece el diálogo UAC**, verificar que `installer.iss` contenga:
```ini
[Setup]
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=no
```

### Test 2: Cancelar UAC
Si haces clic "No", setup.exe se cierra sin instalar. ✅ Correcto.

### Test 3: Aceptar UAC
Si haces clic "Sí", inicia el wizard de instalación con admin. ✅ Correcto.

---

## 📦 Archivos generados

```
agent_local/
├── dist/
│   ├── LocalPrinterAgent.exe              ← EXE sin installer
│   ├── LocalPrinterAgent-Setup.exe        ← ⭐ SETUP FINAL (distribuir esto)
│   └── ...
├── build/                                 ← Temporales (no necesarios)
├── LocalPrinterAgent.spec                 ← Especificación (no editar)
└── ...
```

---

## 🎁 Distribución a usuarios

### Archivo a compartir:
```
dist/LocalPrinterAgent-Setup.exe
```

### Instrucciones para usuarios:
1. Descargar `LocalPrinterAgent-Setup.exe`
2. Hacer doble clic
3. Windows pide permiso (diálogo UAC) → Hacer clic "Sí"
4. Seguir wizard de instalación
5. Hacer clic "Instalar"
6. ¡Listo! LocalPrinterAgent se abre automáticamente

---

## 🐛 Troubleshooting rápido

| Problema | Solución |
|----------|----------|
| **PyInstaller no encontrado** | `pip install pyinstaller` |
| **Inno Setup no encontrado** | Descargar desde https://jrsoftware.org/isdl.php |
| **Setup.exe no pide admin** | Verificar `PrivilegesRequired=admin` en `installer.iss` |
| **Error en build** | Ejecutar `build_setup.ps1 -Clean` para reconstruir desde 0 |
| **dist/ no tiene .exe** | PyInstaller falló; revisar errores de consola |

---

## 📝 Notas importantes

✅ **Admin obligatorio:**
- Configurado en `installer.iss` con `PrivilegesRequired=admin`
- Windows SIEMPRE pide elevación antes de instalar
- El usuario NO puede saltarse este paso

✅ **Icono personalizado:**
- Usar PNG/ICO de 256x256 como mínimo
- Especificado en `installer.iss` con `SetupIconFile=LocalPrinterAgent.ico`

✅ **Actualizaciones futuras:**
- Cambiar versión en `installer.iss`: `AppVersion=1.0.1`
- Regenerar exe y setup.exe
- Nueva versión de setup se genera automáticamente

---

## 📋 Resumen de comandos

```powershell
# Opción rápida (recomendada)
.\build_setup.ps1 -Clean

# O manual:
pyinstaller --noconfirm --onefile --windowed --icon=LocalPrinterAgent.ico LocalPrinterAgent.py
$inno = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
& $inno "installer.iss"

# Resultado
ls dist\LocalPrinterAgent-Setup.exe
```

---

✅ **Done: Ya tienes setup.exe con admin obligatorio**

¿Preguntas? Ver `BUILD_SETUP_GUIDE.md` para más detalles.
