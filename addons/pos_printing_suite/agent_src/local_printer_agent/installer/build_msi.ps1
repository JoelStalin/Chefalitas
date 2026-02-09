param(
    [string]$ZipPath,
    [string]$OutDir = "..\\dist",
    [string]$Version = "1.0.0"
)

$ErrorActionPreference = 'Stop'

function Require-Tool($name) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if (-not $cmd) {
        Write-Host "Missing tool: $name"
        Write-Host "Install WiX Toolset CLI v6: dotnet tool install --global wix"
        exit 1
    }
}

Require-Tool "wix"

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

$iconPath = Join-Path $temp "assets\\agent.ico"
if (-not (Test-Path $iconPath)) {
    $iconPath = Join-Path $PSScriptRoot "..\\assets\\agent.ico"
}

Write-Host "Generating AgentFiles.wxs..."
$components = New-Object System.Collections.Generic.List[string]
$compRefs = New-Object System.Collections.Generic.List[string]
$idx = 0
Get-ChildItem -Path $temp -Recurse -File | ForEach-Object {
    $compId = "cmp$idx"
    $fileId = "fil$idx"
    $src = $_.FullName
    $components.Add("      <Component Id=`"$compId`" Guid=`"*`">`n        <File Id=`"$fileId`" Source=`"$src`" KeyPath=`"yes`" />`n      </Component>")
    $compRefs.Add("      <ComponentRef Id=`"$compId`" />")
    $idx++
}

$wxs = @"
<?xml version="1.0" encoding="UTF-8"?>
<Wix xmlns="http://wixtoolset.org/schemas/v4/wxs">
  <Fragment>
    <DirectoryRef Id="AGENTDIR">
$($components -join "`n")
    </DirectoryRef>
  </Fragment>
  <Fragment>
    <ComponentGroup Id="AgentFilesComponentGroup">
$($compRefs -join "`n")
    </ComponentGroup>
  </Fragment>
</Wix>
"@

Set-Content -Path $harvestWxs -Value $wxs -Encoding UTF8

Write-Host "Building MSI..."
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$msiName = "PosPrintingSuiteAgent-$Version.msi"
$msiPath = Join-Path $OutDir $msiName

& wix build -d ProductVersion=$Version -d IconPath="$iconPath" -o $msiPath $productWxs $harvestWxs

Write-Host "MSI created: $msiPath"
