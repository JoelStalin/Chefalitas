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

$serviceExeCandidates = @(
    (Join-Path $temp "dist\\LocalPrinterAgent\\LocalPrinterAgent.exe"),
    (Join-Path $temp "LocalPrinterAgent.exe"),
    (Join-Path $temp "agent.exe")
)
$serviceExePath = $serviceExeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $serviceExePath) {
    Write-Host "ERROR: Service executable not found in the ZIP. Build the agent first."
    exit 1
}

Write-Host "Generating AgentFiles.wxs..."
$components = New-Object System.Collections.Generic.List[string]
$compRefs = New-Object System.Collections.Generic.List[string]
$idx = 0
Get-ChildItem -Path $temp -Recurse -File | ForEach-Object {
    $compId = "cmp$idx"
    $fileId = "fil$idx"
    $src = $_.FullName
    if ($src -eq $serviceExePath) {
        $components.Add(@"
      <Component Id="$compId" Guid="*">
        <File Id="$fileId" Source="$src" KeyPath="yes" />
        <ServiceInstall Id="PosPrintingSuiteAgentSvc"
                        Name="PosPrintingSuiteAgent"
                        DisplayName="POS Printing Suite Agent"
                        Description="POS Printing Suite Windows Agent"
                        Start="auto"
                        Type="ownProcess"
                        ErrorControl="normal" />
        <ServiceControl Id="PosPrintingSuiteAgentCtrl"
                        Name="PosPrintingSuiteAgent"
                        Stop="both"
                        Remove="uninstall"
                        Wait="yes" />
      </Component>
"@)
    } else {
        $components.Add("      <Component Id=`"$compId`" Guid=`"*`">`n        <File Id=`"$fileId`" Source=`"$src`" KeyPath=`"yes`" />`n      </Component>")
    }
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

Get-ChildItem -Path $OutDir -Filter "cab*.cab" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

& wix build -d ProductVersion=$Version -d IconPath="$iconPath" -o $msiPath $productWxs $harvestWxs
if ($LASTEXITCODE -ne 0) {
    throw "WiX build failed with exit code $LASTEXITCODE"
}

Write-Host "MSI created: $msiPath"
