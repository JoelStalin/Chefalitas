$ErrorActionPreference = 'SilentlyContinue'

Add-Type -AssemblyName System.Windows.Forms | Out-Null
Add-Type -AssemblyName System.Drawing | Out-Null

$serviceName = 'PosPrintingSuiteAgent'
$baseDir = Join-Path $env:ProgramData 'PosPrintingSuite\Agent'
$logDir = Join-Path $baseDir 'logs'
$iconPath = Join-Path $baseDir 'assets\agent.ico'
if (-not (Test-Path $iconPath)) {
    $iconPath = Join-Path $PSScriptRoot 'assets\agent.ico'
}

$notify = New-Object System.Windows.Forms.NotifyIcon
if (Test-Path $iconPath) {
    $notify.Icon = New-Object System.Drawing.Icon($iconPath)
}
$notify.Text = 'POS Printing Suite Agent'
$notify.Visible = $true

$menu = New-Object System.Windows.Forms.ContextMenu
$itemOpenLogs = New-Object System.Windows.Forms.MenuItem 'Open Logs', {
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
    Invoke-Item $logDir
}
$itemStart = New-Object System.Windows.Forms.MenuItem 'Start Service', {
    Start-Service -Name $serviceName -ErrorAction SilentlyContinue | Out-Null
}
$itemStop = New-Object System.Windows.Forms.MenuItem 'Stop Service', {
    Stop-Service -Name $serviceName -Force -ErrorAction SilentlyContinue | Out-Null
}
$itemRestart = New-Object System.Windows.Forms.MenuItem 'Restart Service', {
    Restart-Service -Name $serviceName -Force -ErrorAction SilentlyContinue | Out-Null
}
$itemExit = New-Object System.Windows.Forms.MenuItem 'Exit', {
    $notify.Visible = $false
    [System.Windows.Forms.Application]::Exit()
}
$menu.MenuItems.AddRange(@($itemOpenLogs, $itemStart, $itemStop, $itemRestart, $itemExit))
$notify.ContextMenu = $menu

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 5000
$timer.add_Tick({
    $svc = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
    if ($svc -and $svc.Status -eq 'Running') {
        $notify.Text = 'POS Printing Suite Agent (Running)'
    } else {
        $notify.Text = 'POS Printing Suite Agent (Stopped)'
    }
})
$timer.Start()

[System.Windows.Forms.Application]::Run()
