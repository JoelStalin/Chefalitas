# Installs the Fripick gateway as a scheduled task that starts with Windows and restarts if it stops.
# Run in PowerShell as administrator, in the unzipped folder:  .\install_windows.ps1 -OdooUrl https://... -Token ...
param([Parameter(Mandatory)] [string]$OdooUrl, [Parameter(Mandatory)] [string]$Token, [string]$PrinterHost = "")
$ErrorActionPreference = "Stop"
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { throw "Instale Python 3 desde python.org y vuelva a ejecutar este script." }
$dir = Join-Path $env:ProgramData "FripickGateway"
New-Item -ItemType Directory -Force $dir | Out-Null
Copy-Item (Join-Path $PSScriptRoot "fripick_gateway.py") $dir -Force
@{ ODOO_URL = $OdooUrl; FRIPICK_TOKEN = $Token; PRINTER_HOST = $PrinterHost } | ConvertTo-Json | Set-Content (Join-Path $dir "fripick-gateway.json")
icacls $dir /inheritance:r /grant:r "SYSTEM:(OI)(CI)F" "Administrators:(OI)(CI)F" | Out-Null
$action = New-ScheduledTaskAction -Execute $python -Argument "`"$dir\fripick_gateway.py`""
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName "FripickGateway" -Action $action -Trigger $trigger -Settings $settings -User "SYSTEM" -RunLevel Highest -Force | Out-Null
Start-ScheduledTask -TaskName "FripickGateway"
Write-Host "Fripick gateway instalado y en ejecución (tarea FripickGateway)."
