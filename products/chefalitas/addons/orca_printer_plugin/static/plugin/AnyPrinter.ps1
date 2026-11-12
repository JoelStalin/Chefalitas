# AnyPrinter: servidor local (127.0.0.1) que imprime en cualquier impresora y abre la gaveta. Sin dependencias.
$ErrorActionPreference = 'Stop'
$cfg = Get-Content (Join-Path $PSScriptRoot 'config.json') -Raw | ConvertFrom-Json
Add-Type -TypeDefinition @"
using System; using System.Runtime.InteropServices;
public class RawPrinter {
  [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Ansi)]
  public class DOCINFOA { [MarshalAs(UnmanagedType.LPStr)] public string pDocName; [MarshalAs(UnmanagedType.LPStr)] public string pOutputFile; [MarshalAs(UnmanagedType.LPStr)] public string pDataType; }
  [DllImport("winspool.Drv", EntryPoint="OpenPrinterA", SetLastError=true, CharSet=CharSet.Ansi)] public static extern bool OpenPrinter(string n, out IntPtr h, IntPtr d);
  [DllImport("winspool.Drv", SetLastError=true)] public static extern bool ClosePrinter(IntPtr h);
  [DllImport("winspool.Drv", EntryPoint="StartDocPrinterA", SetLastError=true, CharSet=CharSet.Ansi)] public static extern bool StartDocPrinter(IntPtr h, int l, [In, MarshalAs(UnmanagedType.LPStruct)] DOCINFOA di);
  [DllImport("winspool.Drv", SetLastError=true)] public static extern bool EndDocPrinter(IntPtr h);
  [DllImport("winspool.Drv", SetLastError=true)] public static extern bool StartPagePrinter(IntPtr h);
  [DllImport("winspool.Drv", SetLastError=true)] public static extern bool EndPagePrinter(IntPtr h);
  [DllImport("winspool.Drv", SetLastError=true)] public static extern bool WritePrinter(IntPtr h, byte[] b, int c, out int w);
  // Convierte la imagen monocroma de Odoo (bits seguidos, sin relleno por fila) en comandos ESC/POS GS v 0, por tandas de filas.
  public static byte[] Raster(byte[] src, int w, int h) {
    int bpr = (w + 7) / 8;
    var outl = new System.Collections.Generic.List<byte>();
    int chunk = 128;
    for (int y0 = 0; y0 < h; y0 += chunk) {
      int rows = Math.Min(chunk, h - y0);
      outl.AddRange(new byte[] { 0x1D, 0x76, 0x30, 0x00, (byte)(bpr & 0xFF), (byte)(bpr >> 8), (byte)(rows & 0xFF), (byte)(rows >> 8) });
      var block = new byte[bpr * rows];
      for (int r = 0; r < rows; r++) for (int x = 0; x < w; x++) {
        long bit = (long)(y0 + r) * w + x;
        int si = (int)(bit >> 3);
        if (si < src.Length && ((src[si] >> (7 - (int)(bit & 7))) & 1) == 1) block[r * bpr + (x >> 3)] |= (byte)(0x80 >> (x & 7));
      }
      outl.AddRange(block);
    }
    return outl.ToArray();
  }
  public static bool Send(string printer, byte[] bytes) {
    IntPtr h; if (!OpenPrinter(printer, out h, IntPtr.Zero)) return false;
    var di = new DOCINFOA { pDocName = "AnyPrinter", pDataType = "RAW" };
    bool ok = StartDocPrinter(h, 1, di) && StartPagePrinter(h);
    int w = 0; if (ok) { ok = WritePrinter(h, bytes, bytes.Length, out w); EndPagePrinter(h); EndDocPrinter(h); }
    ClosePrinter(h); return ok;
  }
}
"@

function Get-Target($body) {
  if ($body.ip) { return @{ kind = 'net'; ip = $body.ip; port = $(if ($body.port) { [int]$body.port } else { 9100 }) } }
  $role = $(if ($body.role) { [string]$body.role } else { 'caja' })
  $byRole = $(if ($cfg.roles -and $cfg.roles.$role) { $cfg.roles.$role } else { $null })
  $name = $(if ($body.printer) { $body.printer } elseif ($byRole) { $byRole } elseif ($cfg.printer) { $cfg.printer } else { (Get-CimInstance Win32_Printer | Where-Object Default | Select-Object -First 1).Name })
  if (-not $name) { throw 'No hay impresora predeterminada ni configurada' }
  if ($name -like 'tcp://*') {   # impresora de red: tcp://192.168.1.50:9100
    $hp = ($name -replace '^tcp://', '').Split(':')
    return @{ kind = 'net'; ip = $hp[0]; port = $(if ($hp.Length -gt 1) { [int]$hp[1] } else { 9100 }) }
  }
  return @{ kind = 'usb'; name = $name }
}
# Traduce el XML ePOS-Print que manda Odoo (imagen, corte, gaveta) a comandos ESC/POS.
function Convert-Epos([string]$xmlText) {
  $doc = New-Object Xml.XmlDocument; $doc.LoadXml($xmlText)
  $ep = $doc.SelectSingleNode("//*[local-name()='epos-print']")
  if (-not $ep) { throw 'XML sin epos-print' }
  $buf = New-Object 'System.Collections.Generic.List[byte]'
  $buf.AddRange([byte[]](0x1B, 0x40))
  foreach ($n in $ep.ChildNodes) {
    switch ($n.LocalName) {
      'image' {
        $data = [Convert]::FromBase64String($n.InnerText.Trim())
        $buf.AddRange([RawPrinter]::Raster($data, [int]$n.GetAttribute('width'), [int]$n.GetAttribute('height')))
      }
      'cut' { $buf.AddRange([byte[]](0x1B, 0x64, 0x04, 0x1D, 0x56, 0x42, 0x00)) }
      'pulse' { $buf.AddRange([byte[]](0x1B, 0x70, $(if ($cfg.drawer_pin -eq 1) { 1 } else { 0 }), 0x19, 0xFA)) }
      'feed' { $buf.AddRange([byte[]](0x1B, 0x64, $(if ($n.GetAttribute('line')) { [byte][int]$n.GetAttribute('line') } else { [byte]1 }))) }
      'text' { $buf.AddRange([Text.Encoding]::GetEncoding(437).GetBytes($n.InnerText)) }
    }
  }
  return , $buf.ToArray()
}
function Reply-Epos($ctx, [bool]$ok, [string]$code) {
  $xml = '<?xml version="1.0" encoding="utf-8"?><PrinterResponse><response success="' + $ok.ToString().ToLower() + '" code="' + $code + '" status="0" battery="0"/></PrinterResponse>'
  $b = [Text.Encoding]::UTF8.GetBytes($xml)
  $ctx.Response.StatusCode = 200; $ctx.Response.ContentType = 'text/xml; charset=utf-8'
  $ctx.Response.OutputStream.Write($b, 0, $b.Length); $ctx.Response.Close()
}
function Send-Bytes($target, [byte[]]$bytes) {
  if ($target.kind -eq 'net') {
    $c = New-Object System.Net.Sockets.TcpClient; $c.Connect($target.ip, $target.port)
    $s = $c.GetStream(); $s.Write($bytes, 0, $bytes.Length); $s.Flush(); $c.Close(); return $true
  }
  return [RawPrinter]::Send($target.name, $bytes)
}
function Reply($ctx, [int]$code, $obj) {
  $json = ($obj | ConvertTo-Json -Compress -Depth 5); $buf = [Text.Encoding]::UTF8.GetBytes($json)
  $ctx.Response.StatusCode = $code; $ctx.Response.ContentType = 'application/json'
  $ctx.Response.OutputStream.Write($buf, 0, $buf.Length); $ctx.Response.Close()
}

$l = New-Object System.Net.HttpListener
$portCocina = $(if ($cfg.port_cocina) { [int]$cfg.port_cocina } else { 9051 })
$l.Prefixes.Add("http://127.0.0.1:$($cfg.port)/")
$l.Prefixes.Add("http://127.0.0.1:$portCocina/")
$l.Start()
Write-Host "AnyPrinter escuchando: caja en $($cfg.port), cocina en $portCocina (Ctrl+C para cerrar)"
while ($l.IsListening) {
  $ctx = $l.GetContext()
  try {
    $origin = $ctx.Request.Headers['Origin']
    if ($origin -and ($cfg.origins -contains $origin)) {
      $ctx.Response.Headers.Add('Access-Control-Allow-Origin', $origin)
      $ctx.Response.Headers.Add('Access-Control-Allow-Headers', 'Content-Type, X-Printer-Token')
      $ctx.Response.Headers.Add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
      $ctx.Response.Headers.Add('Access-Control-Allow-Private-Network', 'true')
    }
    if ($ctx.Request.HttpMethod -eq 'OPTIONS') { $ctx.Response.StatusCode = 204; $ctx.Response.Close(); continue }
    $path = $ctx.Request.Url.AbsolutePath
    if ($path -eq '/cgi-bin/epos/service.cgi' -and $ctx.Request.HttpMethod -eq 'POST') {
      # Modo "Impresora ePOS" de Odoo: IP 127.0.0.1:9050 = caja, 127.0.0.1:9051 = cocina. Solo desde el Odoo permitido.
      if (-not ($origin -and ($cfg.origins -contains $origin))) { Reply-Epos $ctx $false 'ORIGEN_NO_PERMITIDO'; continue }
      $xmlText = (New-Object IO.StreamReader($ctx.Request.InputStream, [Text.Encoding]::UTF8)).ReadToEnd()
      $role = $(if ($ctx.Request.LocalEndPoint.Port -eq $portCocina) { 'cocina' } else { 'caja' })
      try {
        $ok = Send-Bytes (Get-Target @{ role = $role }) ([byte[]](Convert-Epos $xmlText))
        Reply-Epos $ctx ([bool]$ok) $(if ($ok) { '' } else { 'PRINTER_ERROR' })
      } catch { Reply-Epos $ctx $false 'DeviceNotFound' }
      continue
    }
    if ($path -eq '/ping') { Reply $ctx 200 @{ ok = $true; name = 'AnyPrinter' }; continue }
    if ($path -eq '/' -and $ctx.Request.HttpMethod -eq 'GET') {
      $names = @(Get-CimInstance Win32_Printer | ForEach-Object { $_.Name })
      $opts = { param($sel) (@('<option value="">(la predeterminada de Windows)</option>') + ($names | ForEach-Object { '<option' + $(if ($_ -eq $sel) { ' selected' } else { '' }) + '>' + [Net.WebUtility]::HtmlEncode($_) + '</option>' })) -join '' }
      $html = '<!doctype html><meta charset="utf-8"><title>AnyPrinter</title><body style="font-family:sans-serif;max-width:520px;margin:40px auto"><h2>AnyPrinter</h2><p>Escoja que impresora usa cada puesto:</p>' +
        '<p><b>Impresora de caja</b> (ticket y gaveta)<br><select id="caja" style="width:100%;padding:6px">' + (& $opts $cfg.roles.caja) + '</select></p>' +
        '<p><b>Impresora de cocina</b><br><select id="cocina" style="width:100%;padding:6px">' + (& $opts $cfg.roles.cocina) + '</select></p>' +
        '<p style="background:#eef;padding:8px;border-radius:6px">En Odoo (Punto de venta > Impresoras): tipo <b>Impresora ePOS</b>, marque <b>Acceso a red local</b>, y en la IP escriba <b>127.0.0.1:9050</b> para la impresora de caja o <b>127.0.0.1:9051</b> para la de cocina.</p>' +
        '<button onclick="save()" style="padding:8px 16px">Guardar</button> <button data-r="caja" onclick="test(this.dataset.r)" style="padding:8px 16px">Probar caja (abre gaveta)</button> <button data-r="cocina" onclick="test(this.dataset.r)" style="padding:8px 16px">Probar cocina</button><p id="m"></p>' +
        '<script>const T="' + $cfg.token + '";async function call(p,b){const r=await fetch(p,{method:"POST",headers:{"X-Printer-Token":T,"Content-Type":"application/json"},body:JSON.stringify(b)});return r.json()}' +
        'async function save(){const r=await call("/set-printers",{caja:document.getElementById("caja").value,cocina:document.getElementById("cocina").value});document.getElementById("m").textContent=r.ok?"Guardado.":"Error: "+r.error}' +
        'async function test(role){const r=await call("/test",{role:role});document.getElementById("m").textContent=r.ok?"Enviado a la impresora de "+role:"Error: "+r.error}</script>'
      $buf = [Text.Encoding]::UTF8.GetBytes($html); $ctx.Response.ContentType = 'text/html; charset=utf-8'
      $ctx.Response.OutputStream.Write($buf, 0, $buf.Length); $ctx.Response.Close(); continue
    }
    if ($ctx.Request.Headers['X-Printer-Token'] -ne $cfg.token) { Reply $ctx 401 @{ ok = $false; error = 'token invalido' }; continue }
    $body = @{}
    if ($ctx.Request.HasEntityBody) { $body = (New-Object IO.StreamReader($ctx.Request.InputStream)).ReadToEnd() | ConvertFrom-Json }
    switch ($path) {
      '/printers' { Reply $ctx 200 @{ ok = $true; printers = @(Get-CimInstance Win32_Printer | ForEach-Object { @{ name = $_.Name; default = [bool]$_.Default } }) } }
      '/set-printers' {
        $cfg.roles = [pscustomobject]@{ caja = [string]$body.caja; cocina = [string]$body.cocina }
        $cfg | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $PSScriptRoot 'config.json') -Encoding UTF8
        Reply $ctx 200 @{ ok = $true }
      }
      '/test' {
        $txt = [Text.Encoding]::ASCII.GetBytes("`n  AnyPrinter - prueba de impresion`n  Impresora: $($body.role)`n`n`n`n")
        $cut = [byte[]](0x1D, 0x56, 0x42, 0x00)
        $drawer = $(if ($body.role -ne 'cocina') { [byte[]](0x1B, 0x70, $(if ($cfg.drawer_pin -eq 1) { 1 } else { 0 }), 0x19, 0xFA) } else { [byte[]]@() })
        $ok = Send-Bytes (Get-Target $body) ([byte[]]($txt + $cut + $drawer))
        Reply $ctx 200 @{ ok = [bool]$ok }
      }
      '/open-drawer' {
        $pin = $(if ($cfg.drawer_pin -eq 1) { 1 } else { 0 })
        $ok = Send-Bytes (Get-Target $body) ([byte[]](0x1B, 0x70, $pin, 0x19, 0xFA))
        Reply $ctx 200 @{ ok = [bool]$ok }
      }
      '/print' {
        $ok = Send-Bytes (Get-Target $body) ([Convert]::FromBase64String($body.data))
        Reply $ctx 200 @{ ok = [bool]$ok }
      }
      default { Reply $ctx 404 @{ ok = $false; error = 'ruta desconocida' } }
    }
  } catch {
    try { Reply $ctx 500 @{ ok = $false; error = $_.Exception.Message } } catch {}
  }
}
