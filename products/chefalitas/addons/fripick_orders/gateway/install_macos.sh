#!/bin/bash
# Installs the Fripick gateway as a launchd service (starts at login, restarts if it stops).
# Usage: ./install_macos.sh https://odoo.example.com <token> [printer-ip]
set -euo pipefail
ODOO_URL=${1:?Uso: install_macos.sh <odoo-url> <token> [ip-impresora]}
TOKEN=${2:?Falta el token}
HOST=${3:-}
DIR="$HOME/Library/Application Support/FripickGateway"
mkdir -p "$DIR"
cp "$(dirname "$0")/fripick_gateway.py" "$DIR/"
umask 077
printf '{"ODOO_URL": "%s", "FRIPICK_TOKEN": "%s", "PRINTER_HOST": "%s"}\n' "$ODOO_URL" "$TOKEN" "$HOST" > "$DIR/fripick-gateway.json"
PLIST="$HOME/Library/LaunchAgents/com.getupsoft.fripick-gateway.plist"
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.getupsoft.fripick-gateway</string>
  <key>ProgramArguments</key><array><string>/usr/bin/python3</string><string>$DIR/fripick_gateway.py</string></array>
  <key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
  <key>StandardErrorPath</key><string>$DIR/gateway.log</string>
</dict></plist>
PL
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "Fripick gateway instalado (launchd com.getupsoft.fripick-gateway)."
