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

$form = New-Object System.Windows.Forms.Form
$form.Text = 'POS Printing Suite Agent'
$form.Width = 620
$form.Height = 420
$form.StartPosition = 'CenterScreen'

$statusLabel = New-Object System.Windows.Forms.Label
$statusLabel.AutoSize = $true
$statusLabel.Text = 'Status: Unknown'
$statusLabel.Location = New-Object System.Drawing.Point(12, 12)
$form.Controls.Add($statusLabel)

$btnStart = New-Object System.Windows.Forms.Button
$btnStart.Text = 'Start'
$btnStart.Width = 80
$btnStart.Location = New-Object System.Drawing.Point(12, 40)
$btnStart.Add_Click({ Start-Service -Name $serviceName -ErrorAction SilentlyContinue | Out-Null })
$form.Controls.Add($btnStart)

$btnStop = New-Object System.Windows.Forms.Button
$btnStop.Text = 'Stop'
$btnStop.Width = 80
$btnStop.Location = New-Object System.Drawing.Point(100, 40)
$btnStop.Add_Click({ Stop-Service -Name $serviceName -Force -ErrorAction SilentlyContinue | Out-Null })
$form.Controls.Add($btnStop)

$btnRestart = New-Object System.Windows.Forms.Button
$btnRestart.Text = 'Restart'
$btnRestart.Width = 80
$btnRestart.Location = New-Object System.Drawing.Point(188, 40)
$btnRestart.Add_Click({ Restart-Service -Name $serviceName -Force -ErrorAction SilentlyContinue | Out-Null })
$form.Controls.Add($btnRestart)

$btnRefresh = New-Object System.Windows.Forms.Button
$btnRefresh.Text = 'Refresh Log'
$btnRefresh.Width = 120
$btnRefresh.Location = New-Object System.Drawing.Point(276, 40)
$form.Controls.Add($btnRefresh)

$logBox = New-Object System.Windows.Forms.TextBox
$logBox.Multiline = $true
$logBox.ScrollBars = 'Vertical'
$logBox.ReadOnly = $true
$logBox.WordWrap = $false
$logBox.Width = 580
$logBox.Height = 290
$logBox.Location = New-Object System.Drawing.Point(12, 80)
$form.Controls.Add($logBox)

function Get-ServiceStatusText {
    $svc = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
    if ($svc) { return $svc.Status.ToString() }
    return 'Not Installed'
}

function Refresh-LogBox {
    $logFile = Join-Path $logDir 'agent.log'
    if (Test-Path $logFile) {
        try {
            $content = Get-Content $logFile -Tail 200
            $logBox.Text = ($content -join [Environment]::NewLine)
        } catch {
            $logBox.Text = 'Unable to read log file.'
        }
    } else {
        $logBox.Text = 'Log file not found.'
    }
}

$btnRefresh.Add_Click({
    Refresh-LogBox
})

$form.Add_Shown({
    $statusLabel.Text = 'Status: ' + (Get-ServiceStatusText)
    Refresh-LogBox
})

$menu = New-Object System.Windows.Forms.ContextMenu
$itemOpenLogs = New-Object System.Windows.Forms.MenuItem 'Open Logs', {
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
    Invoke-Item $logDir
}
$itemOpenUi = New-Object System.Windows.Forms.MenuItem 'Open Control Panel', {
    $form.Show()
    $form.BringToFront()
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
$menu.MenuItems.AddRange(@($itemOpenUi, $itemOpenLogs, $itemStart, $itemStop, $itemRestart, $itemExit))
$notify.ContextMenu = $menu

$notify.add_DoubleClick({
    $form.Show()
    $form.BringToFront()
})

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 5000
$timer.add_Tick({
    $svc = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
    if ($svc -and $svc.Status -eq 'Running') {
        $notify.Text = 'POS Printing Suite Agent (Running)'
    } else {
        $notify.Text = 'POS Printing Suite Agent (Stopped)'
    }
    $statusLabel.Text = 'Status: ' + (Get-ServiceStatusText)
})
$timer.Start()

[System.Windows.Forms.Application]::Run()
