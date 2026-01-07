# 📊 Diagrama del Proceso Completo

## 🔄 Flujo de Compilación

```
┌─────────────────────────────────────────────────────────────┐
│ 1. PREPARACIÓN                                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ✅ Python 3.10+                                           │
│  ✅ PyInstaller (pip install pyinstaller)                  │
│  ✅ Inno Setup 6.3+ (https://jrsoftware.org/isdl.php)     │
│                                                             │
│  Archivos en agent_local/:                                 │
│  ✅ LocalPrinterAgent.py                                   │
│  ✅ LocalPrinterAgent.ico (256x256)                        │
│  ✅ installer.iss                                          │
│  ✅ README_INSTALLATION.md                                 │
│  ✅ LICENSE.txt                                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. GENERAR EXE CON PYINSTALLER                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  $ pyinstaller --onefile --windowed \                      │
│      --icon=LocalPrinterAgent.ico \                        │
│      LocalPrinterAgent.py                                  │
│                                                             │
│  Genera:                                                    │
│  ✅ dist/LocalPrinterAgent.exe (~ 50-100 MB)              │
│  ✅ build/ (temporales)                                    │
│  ✅ LocalPrinterAgent.spec                                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. COMPILAR SETUP.EXE CON INNO SETUP                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  $ C:\Program Files (x86)\Inno Setup 6\ISCC.exe \          │
│      installer.iss                                         │
│                                                             │
│  installer.iss contiene:                                   │
│  ✅ PrivilegesRequired=admin (admin OBLIGATORIO)           │
│  ✅ App name, version, publisher                           │
│  ✅ Archivos a instalar                                    │
│  ✅ Accesos directos                                       │
│  ✅ Desinstalador                                          │
│                                                             │
│  Genera:                                                    │
│  ✅ dist/LocalPrinterAgent-Setup.exe (~ 50-100 MB)        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ ✅ RESULTADO: dist/LocalPrinterAgent-Setup.exe             │
│    (Listo para distribuir a usuarios)                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 Flujo de EJECUCIÓN del Setup.exe

```
Usuario hace doble clic en:
dist/LocalPrinterAgent-Setup.exe

         ↓

┌─────────────────────────────────────┐
│ Windows analiza la aplicación       │
│ Detecta: PrivilegesRequired=admin   │
└─────────────────────────────────────┘

         ↓

┌──────────────────────────────────────────────┐
│ 🔐 DIÁLOGO UAC (ADMINISTRADOR REQUERIDO)   │
│                                              │
│  "¿Deseas permitir que esta aplicación      │
│   realice cambios en tu dispositivo?"        │
│                                              │
│              [No]  [Sí]                     │
└──────────────────────────────────────────────┘
  ↓                            ↓
CANCELA                    CONTINÚA
  │                            │
  ↓                            ↓
┌──────────────┐      ┌───────────────────────┐
│ Setup.exe    │      │ Abre wizard con ADMIN │
│ se cierra    │      │ (ya elevado)          │
│ sin instalar │      └───────────────────────┘
└──────────────┘              ↓
                      ┌───────────────────────┐
                      │ Seleccionar componentes:
                      │ ✓ Aplicación         │
                      │ ✓ Servicio Windows   │
                      │ ✓ Acceso directo     │
                      └───────────────────────┘
                              ↓
                      ┌───────────────────────┐
                      │ Elegir carpeta:      │
                      │ C:\Program Files\    │
                      │ LocalPrinterAgent\   │
                      └───────────────────────┘
                              ↓
                      ┌───────────────────────┐
                      │ [Instalar]            │
                      │                       │
                      │ Copia archivos:       │
                      │ ✓ EXE                │
                      │ ✓ Icono              │
                      │ ✓ Dependencias       │
                      │ ✓ Config             │
                      └───────────────────────┘
                              ↓
                      ┌───────────────────────┐
                      │ [Terminar]            │
                      │                       │
                      │ Crea accesos directos:
                      │ ✓ Menú Inicio         │
                      │ ✓ Escritorio         │
                      │                       │
                      │ Ejecuta app           │
                      └───────────────────────┘
```

---

## 📁 Estructura de carpetas finales

### Durante el proceso:
```
agent_local/
├── LocalPrinterAgent.py                ← Script principal
├── LocalPrinterAgent.ico               ← Icono
├── installer.iss                       ← Script de Inno Setup
├── build_setup.ps1                     ← Script automático
├── BUILD_SETUP_GUIDE.md                ← Guía completa
├── QUICK_SETUP_GUIDE.md                ← Guía rápida
├── README_INSTALLATION.md              ← Instrucciones instalación
├── LICENSE.txt                         ← Licencia
├── service_config.json                 ← Config servicio
│
├── build/                              ← Temporales (PyInstaller)
│   └── LocalPrinterAgent/
│       └── ... (archivos temporales)
│
├── dist/                               ← SALIDA FINAL
│   ├── LocalPrinterAgent.exe           ← EXE (sin installer)
│   ├── LocalPrinterAgent-Setup.exe     ← ⭐ SETUP (distribuir)
│   └── LocalPrinterAgent/              ← Dependencias (si --onedir)
│
└── LocalPrinterAgent.spec              ← Especificación PyInstaller
```

### Después de instalar en usuario:
```
C:\Program Files\LocalPrinterAgent\
├── LocalPrinterAgent.exe               ← Ejecutable
├── LocalPrinterAgent.ico               ← Icono
├── service_config.json                 ← Config
├── README.md                           ← Documentación
└── ... (dependencias dll/py)

C:\ProgramData\Microsoft\Windows\Start Menu\Programs\
└── LocalPrinterAgent/
    └── LocalPrinterAgent.lnk           ← Acceso directo
```

---

## ⚙️ Cómo funciona "Admin Obligatorio"

```
┌────────────────────────────────────────────────────────┐
│ installer.iss contiene:                                │
│                                                        │
│ [Setup]                                                │
│ PrivilegesRequired=admin                               │
│ PrivilegesRequiredOverridesAllowed=no                  │
│                                                        │
│ Esto significa:                                        │
│ • admin = Requiere permisos de administrador           │
│ • =no   = NO se puede saltarse                         │
└────────────────────────────────────────────────────────┘

         ↓

ISCC.exe (compilador Inno Setup) INCRUSTA ESTO en el .exe

         ↓

Cuando Windows ejecuta setup.exe:
1. Lee la información del binario
2. Ve: "PrivilegesRequired=admin"
3. Pide confirmación al usuario (diálogo UAC)
4. Si acepta → ejecuta con permisos elevados
5. Si rechaza → se cierra sin instalar
```

---

## 🔐 Por qué es más seguro así

```
❌ MÉTODO ANTIGUO (sin UAC):
   setup.exe inicia
   → Instala archivos en C:\
   → El usuario se da cuenta cuando es tarde

✅ MÉTODO NUEVO (con UAC):
   setup.exe inicia
   → Windows pide confirmación INMEDIATO
   → El usuario SABE que está instalando algo
   → Si no quiere, cierra sin instalar nada
```

---

## 📊 Comparativa: setup.exe vs LocalPrinterAgent.exe

| Aspecto | setup.exe | LocalPrinterAgent.exe |
|---------|-----------|----------------------|
| **Usa para** | Instalar la app | Ejecutar la app |
| **Requiere admin** | SÍ (al instalar) | SÍ (si se especifica en installer.iss) |
| **Se ejecuta una vez** | SÍ | NO (cada vez que se abre) |
| **Pide UAC** | SIEMPRE | Solo si se ejecuta manualmente |
| **Tamaño** | ~ 50-100 MB | ~ 50-100 MB |
| **A distribuir** | setup.exe | NO (se instala en Program Files) |

---

## 🚀 Flujo completo (timeline)

```
T=0s:    Usuario descarga dist/LocalPrinterAgent-Setup.exe
         Tamaño: ~80 MB
         
T=5s:    Usuario hace doble clic en el archivo
         
T=6s:    Windows verifica el binario
         Lee: "PrivilegesRequired=admin"
         
T=7s:    🔐 Muestra diálogo UAC
         "¿Permitir cambios en tu dispositivo?"
         
T=10s:   Usuario hace clic "Sí"
         (Si hace clic "No", aquí termina)
         
T=11s:   Se abre Inno Setup Wizard
         - Seleccionar componentes
         - Elegir carpeta destino
         - Revisar instalación
         
T=20s:   Usuario hace clic "Instalar"
         Inno Setup copia archivos
         Crea accesos directos
         
T=30s:   Usuario hace clic "Terminar"
         LocalPrinterAgent.exe se abre automáticamente
         
T=31s:   ✅ INSTALACIÓN COMPLETADA
         App lista para usar
```

---

## ✅ Verificación post-instalación

```powershell
# Verificar que los archivos están en su lugar
Test-Path "C:\Program Files\LocalPrinterAgent\LocalPrinterAgent.exe"
Test-Path "C:\Program Files\LocalPrinterAgent\LocalPrinterAgent.ico"

# Verificar acceso directo en menú inicio
Test-Path "$env:PROGRAMDATA\Microsoft\Windows\Start Menu\Programs\LocalPrinterAgent"

# Ejecutar desde línea de comandos
C:\Program Files\LocalPrinterAgent\LocalPrinterAgent.exe
```

---

**Listo para distribuir tu setup.exe profesional con admin obligatorio!**

