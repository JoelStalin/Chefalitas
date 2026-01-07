# PASO CRÍTICO: Instalar Inno Setup 6.3+

## Estado actual
```
✓ Python 3.10 está instalado
✓ PyInstaller 6.16.0 está instalado
✗ Inno Setup 6.3+ NO ESTÁ INSTALADO  ← NECESARIO DESCARGAR
```

## ¿Qué es Inno Setup?
Inno Setup es la herramienta que **convierte** el ejecutable `LocalPrinterAgent.exe` en un **instalador profesional** `setup.exe` con admin obligatorio.

## Descarga e Instalación de Inno Setup

### 1. Descargar
```
URL: https://jrsoftware.org/isdl.php
Archivo: jsetup-6.3.0.exe (o versión más reciente)
Tamaño: ~5 MB
```

### 2. Instalar (pasos)
```
1. Doble clic en jsetup-6.3.0.exe
2. Click "Next" varias veces
3. IMPORTANTE: Marcar "Install Inno Setup Preprocessor"
4. Ubicación predeterminada: C:\Program Files (x86)\Inno Setup 6\
5. Click "Finish"
```

### 3. Verificar instalación
```powershell
# En PowerShell, ejecuta:
Test-Path "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

# Debe mostrar: True
```

---

## Después de instalar Inno Setup

Una vez instalado, ejecuta:

```powershell
cd C:\Users\yoeli\Documents\Chefalitas\agent_local
powershell -ExecutionPolicy Bypass -File build_simple.ps1 -Clean
```

**El script hará automáticamente:**
1. ✓ Limpiar builds anteriores
2. ✓ Generar exe con PyInstaller
3. ✓ Compilar setup.exe con Inno Setup
4. ✓ Mostrar resultado final

---

## Resultado esperado

```
=== COMPILACION COMPLETADA CON EXITO ===

Archivos generados:
  - Ejecutable:   dist\LocalPrinterAgent.exe
  - Instalador:   dist\LocalPrinterAgent-Setup.exe

Pasos siguientes:
  1. Ejecuta: .\dist\LocalPrinterAgent-Setup.exe
  2. Windows debe mostrar dialogo UAC pidiendo admin
  3. Distribuye dist\LocalPrinterAgent-Setup.exe a usuarios
```

---

## Links útiles

- Inno Setup Descargas: https://jrsoftware.org/isdl.php
- Documentación Inno Setup: https://jrsoftware.org/isinfo.php

---

**Acción requerida:** Descargar e instalar Inno Setup, luego ejecutar build_simple.ps1
