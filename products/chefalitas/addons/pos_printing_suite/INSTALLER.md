# POS Printing Suite Agent (MSI) - Build & Troubleshooting

This document explains how to build the Windows MSI installer for the
POS Printing Suite Agent, and how to collect logs if installation fails.

## Location

- MSI project (WiX v4): `agent_src/local_printer_agent/installer/wix/Product.wxs`
- MSI build script: `agent_src/local_printer_agent/installer/build_msi.ps1`
- Agent build script: `agent_src/local_printer_agent/installer/build.ps1`
- Output folder: `agent_src/dist/`

## Prerequisites (Windows)

- Python 3.10+ (x64 recommended)
- WiX Toolset v4+ (CLI v6 recommended)
  - Install: `dotnet tool install --global wix`
- PyInstaller + pywin32 + Pillow:
  - `python -m pip install pyinstaller pywin32 pillow`

## Build steps (recommended)

1) Build the agent executable (onedir):
```powershell
cd addons/pos_printing_suite/agent_src/local_printer_agent/installer
.\build.ps1
```
This creates:
`agent_src/local_printer_agent/dist/LocalPrinterAgent/LocalPrinterAgent.exe`

2) Get the agent ZIP bundle (from Odoo UI or local packaging).
If you use Odoo, it generates `windows_agent_v0.1.0.zip`.

3) Build the MSI:
```powershell
cd addons/pos_printing_suite/agent_src/local_printer_agent/installer
.\build_msi.ps1 -ZipPath "C:\Path\windows_agent_v0.1.0.zip" -OutDir "..\dist" -Version "1.0.5"
```
MSI output:
`addons/pos_printing_suite/agent_src/dist/PosPrintingSuiteAgent-1.0.5.msi`

## Install / Uninstall logs (MSI)

Install:
```bat
msiexec /i "C:\Path\PosPrintingSuiteAgent-1.0.5.msi" /L*V "%TEMP%\agent_install.log"
```

Uninstall:
```bat
msiexec /x "C:\Path\PosPrintingSuiteAgent-1.0.5.msi" /L*V "%TEMP%\agent_uninstall.log"
```

## Troubleshooting

### Local legacy receiver (debug/testing)
If you need to test POS print payloads locally and save them as PDF files:

```powershell
cd addons/pos_printing_suite/agent_src/local_printer_agent/tools
python legacy_pdf_receiver.py
```

By default it listens on `http://127.0.0.1:9060` and writes files to `tmp/print_jobs`.

### cab1.cab not found
- Ensure the MSI is built with embedded CAB:
  `MediaTemplate EmbedCab="yes"` and `Compressed="yes"` in `Product.wxs`.
- Remove old `cab*.cab` files before building.

### "There is a problem with this Windows Installer package..."
Typical causes:
- Custom Actions running during install (remove or fix).
- Service start attempted during install.
- Missing elevation (not running as admin).

Current MSI should:
- Use `ServiceInstall` / `ServiceControl` (no Custom Actions).
- **Not** start the service during install.
- Use `Scope="perMachine"` (will prompt for admin/UAC).

### MSI installs but service not running
Start it manually:
```powershell
Start-Service PosPrintingSuiteAgent
```
The service is set to auto-start on reboot.

## Notes

- Odoo selects the newest MSI from `agent_src/dist/`.
- If you have multiple MSI files, remove old ones to avoid confusion.
