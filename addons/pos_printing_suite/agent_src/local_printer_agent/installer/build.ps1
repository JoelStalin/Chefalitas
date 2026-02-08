# Build Local Printer Agent (onedir). Run from repo root or agent_src/local_printer_agent.
# Usage: .\build.ps1 [-Token "optional_token"]
param([string]$Token = "REPLACE_ME")
$ErrorActionPreference = "Stop"
$agentDir = $PSScriptRoot
if ($agentDir -match "installer$") { $agentDir = Split-Path $agentDir -Parent }
Set-Location $agentDir
& python -m pip install pyinstaller pywin32 pillow pymupdf --quiet
New-Item -ItemType Directory -Force -Path build, dist | Out-Null
& python -m PyInstaller --clean --noconfirm (Join-Path $agentDir "installer\pyinstaller.spec")
Write-Host "Built. Output in dist\LocalPrinterAgent\"
Write-Host "Create config with token in ProgramData\PosPrintingSuite\Agent\config.json: `"token`": `"$Token`""
