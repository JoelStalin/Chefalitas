#!/data/data/com.termux/files/usr/bin/bash
# Android tablet: install Termux and Termux:Boot (F-Droid), then run in Termux:
#   pkg install python && bash install_android_termux.sh https://odoo.example.com <token> <printer-ip>
# The gateway starts with the tablet (Termux:Boot) and keeps the screen-off wake lock.
set -euo pipefail
ODOO_URL=${1:?Uso: install_android_termux.sh <odoo-url> <token> <ip-impresora>}
TOKEN=${2:?Falta el token}
HOST=${3:?Falta la IP de la impresora}
DIR="$HOME/fripick-gateway"
mkdir -p "$DIR" "$HOME/.termux/boot"
cp "$(dirname "$0")/fripick_gateway.py" "$DIR/"
umask 077
printf '{"ODOO_URL": "%s", "FRIPICK_TOKEN": "%s", "PRINTER_HOST": "%s"}\n' "$ODOO_URL" "$TOKEN" "$HOST" > "$DIR/fripick-gateway.json"
cat > "$HOME/.termux/boot/fripick-gateway.sh" <<BOOT
#!/data/data/com.termux/files/usr/bin/sh
termux-wake-lock
cd "$DIR" && exec python fripick_gateway.py >> gateway.log 2>&1
BOOT
chmod 700 "$HOME/.termux/boot/fripick-gateway.sh"
nohup sh "$HOME/.termux/boot/fripick-gateway.sh" >/dev/null 2>&1 &
echo "Fripick gateway instalado; arranca con la tableta (Termux:Boot)."
