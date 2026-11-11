# Captura lo que manda una bascula (por red o por puerto serie) y lo guarda en un archivo, sin interpretarlo.
# Sirve para conocer el formato real de la bascula (por ejemplo la Merkato MK-A01) antes de leerla desde AnyPrinter.
#
# Uso:
#   .\capturar_bascula.ps1 -Tcp 192.168.1.50:4001            (bascula por red)
#   .\capturar_bascula.ps1 -Com COM3 -Baud 9600               (bascula por cable serie/USB)
#   .\capturar_bascula.ps1 -Tcp 192.168.1.50:4001 -Enviar 'W\r\n'   (si la bascula solo responde cuando se le pide el peso)
# Pon un peso sobre la bascula mientras corre y quitalo despues. Al terminar, manda el archivo captura_bascula_*.txt.
param(
    [string]$Tcp = '',
    [string]$Com = '',
    [int]$Baud = 9600,
    [int]$Segundos = 60,
    [string]$Enviar = '',
    [string]$Salida = ''
)

$ErrorActionPreference = 'Stop'
if (-not $Tcp -and -not $Com) {
    Write-Host 'Indica -Tcp IP:PUERTO o -Com COMx. Ejemplo: .\capturar_bascula.ps1 -Tcp 192.168.1.50:4001'
    exit 1
}
if (-not $Salida) { $Salida = Join-Path $PSScriptRoot ('captura_bascula_{0:yyyyMMdd_HHmmss}.txt' -f (Get-Date)) }

function Escribir([string]$linea) {
    Add-Content -Path $Salida -Value $linea -Encoding UTF8
    Write-Host $linea
}

function Formato([byte[]]$b) {
    $hex = ($b | ForEach-Object { $_.ToString('X2') }) -join ' '
    $asc = -join ($b | ForEach-Object { if ($_ -ge 32 -and $_ -le 126) { [char]$_ } else { '.' } })
    return ('{0:HH:mm:ss.fff}  {1} bytes | {2} | {3}' -f (Get-Date), $b.Length, $hex, $asc)
}

# convierte \r \n \t escritos como texto en los caracteres reales
function Texto([string]$s) { return ($s -replace '\\r', "`r" -replace '\\n', "`n" -replace '\\t', "`t") }

$destino = if ($Tcp) { "TCP $Tcp" } else { "serie $Com a $Baud baudios 8N1" }
Escribir ("# Captura de bascula {0:yyyy-MM-dd HH:mm:ss}  destino: {1}  duracion: {2}s" -f (Get-Date), $destino, $Segundos)
if ($Enviar) { Escribir ("# Se envia al iniciar: {0}" -f $Enviar) }

$total = 0
$cliente = $null
$puerto = $null
try {
    if ($Tcp) {
        $partes = $Tcp.Split(':')
        if ($partes.Length -ne 2) { throw 'Usa el formato IP:PUERTO, por ejemplo 192.168.1.50:4001' }
        $cliente = New-Object System.Net.Sockets.TcpClient
        $conexion = $cliente.BeginConnect($partes[0], [int]$partes[1], $null, $null)
        if (-not $conexion.AsyncWaitHandle.WaitOne(5000)) { throw "No se pudo conectar a $Tcp en 5 segundos" }
        $cliente.EndConnect($conexion)
        $flujo = $cliente.GetStream()
        Escribir '# Conectado.'
        if ($Enviar) { $datos = [System.Text.Encoding]::ASCII.GetBytes((Texto $Enviar)); $flujo.Write($datos, 0, $datos.Length) }
        $fin = (Get-Date).AddSeconds($Segundos)
        $buffer = New-Object byte[] 1024
        while ((Get-Date) -lt $fin) {
            if ($flujo.DataAvailable) {
                $n = $flujo.Read($buffer, 0, $buffer.Length)
                if ($n -le 0) { Escribir '# La bascula cerro la conexion.'; break }
                $trozo = New-Object byte[] $n
                [Array]::Copy($buffer, $trozo, $n)
                $total += $n
                Escribir (Formato $trozo)
            } else { Start-Sleep -Milliseconds 50 }
        }
    } else {
        $puerto = New-Object System.IO.Ports.SerialPort $Com, $Baud, ([System.IO.Ports.Parity]::None), 8, ([System.IO.Ports.StopBits]::One)
        $puerto.ReadTimeout = 500
        $puerto.Open()
        Escribir '# Puerto abierto.'
        if ($Enviar) { $puerto.Write((Texto $Enviar)) }
        $fin = (Get-Date).AddSeconds($Segundos)
        while ((Get-Date) -lt $fin) {
            $n = $puerto.BytesToRead
            if ($n -gt 0) {
                $trozo = New-Object byte[] $n
                [void]$puerto.Read($trozo, 0, $n)
                $total += $n
                Escribir (Formato $trozo)
            } else { Start-Sleep -Milliseconds 50 }
        }
    }
} catch {
    Escribir ("# ERROR: {0}" -f $_.Exception.Message)
} finally {
    if ($cliente) { $cliente.Close() }
    if ($puerto -and $puerto.IsOpen) { $puerto.Close() }
}

Escribir ("# Fin. Bytes recibidos: {0}" -f $total)
if ($total -eq 0) { Escribir '# No llego nada: prueba con -Enviar para pedir el peso, revisa la IP/puerto o los baudios, y que haya peso sobre la bascula.' }
Write-Host ''
Write-Host ('Archivo guardado en: ' + $Salida)
