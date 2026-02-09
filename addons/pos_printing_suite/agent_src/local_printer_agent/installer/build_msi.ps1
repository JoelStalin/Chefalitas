$ErrorActionPreference = 'Stop'

param(
    [string]$ZipPath,
    [string]$OutDir = "..\\dist",
    [string]$Version = "1.0.0"
)

function Require-Tool($name) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if (-not $cmd) {
        Write-Host "Missing tool: $name"
        Write-Host "Install WiX Toolset v3+ and ensure candle.exe/light.exe/heat.exe are in PATH."
        exit 1
    }
}

Require-Tool "candle.exe"
Require-Tool "light.exe"
Require-Tool "heat.exe"

if (-not $ZipPath) {
    Write-Host "Usage: build_msi.ps1 -ZipPath <agent_zip_from_odoo> [-OutDir <dist>] [-Version <x.y.z>]"
    exit 1
}

$zipFull = Resolve-Path $ZipPath
$temp = Join-Path $env:TEMP ("pos_printing_suite_msi_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $temp | Out-Null

Write-Host "Extracting $zipFull -> $temp"
Expand-Archive -Force $zipFull -DestinationPath $temp

$productWxs = Join-Path $PSScriptRoot "wix\\Product.wxs"
$harvestWxs = Join-Path $temp "AgentFiles.wxs"
$objDir = Join-Path $temp "obj"
New-Item -ItemType Directory -Force -Path $objDir | Out-Null

$iconPath = Join-Path $temp "assets\\agent.ico"
if (-not (Test-Path $iconPath)) {
    $iconPath = Join-Path $PSScriptRoot "..\\assets\\agent.ico"
}

Write-Host "Harvesting files..."
& heat.exe dir $temp -srd -cg AgentFilesComponentGroup -dr AGENTDIR -gg -scom -sreg -sfrag -template fragment -out $harvestWxs

Write-Host "Compiling..."
& candle.exe -dProductVersion=$Version -dIconPath="$iconPath" -out "$objDir\\" $productWxs $harvestWxs

Write-Host "Linking..."
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$msiName = "PosPrintingSuiteAgent-$Version.msi"
$msiPath = Join-Path $OutDir $msiName
& light.exe -out $msiPath "$objDir\\Product.wixobj" "$objDir\\AgentFiles.wixobj" -ext WixUIExtension -ext WixUtilExtension

Write-Host "MSI created: $msiPath"
