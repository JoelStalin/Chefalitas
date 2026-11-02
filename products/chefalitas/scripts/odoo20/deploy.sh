#!/usr/bin/env bash
# Despliegue de produccion de Odoo 20 (lo ejecuta el workflow deploy-prod-odoo20.yml en el runner del servidor de produccion).
# Copia el codigo a DEPLOY_DIR (los secretos y volumenes de DEPLOY_DIR se conservan), construye la imagen, actualiza modulos y verifica.
set -euo pipefail
DEPLOY_DIR="${DEPLOY_DIR:-/opt/chefalitas-odoo20}"
SRC="$(cd "$(dirname "$0")/../.." && pwd)"
mkdir -p "$DEPLOY_DIR"
cd "$SRC"
tar --exclude=.git --exclude=.env --exclude='db_data' --exclude='backups' --exclude='tmp' -cf - . | tar -xf - -C "$DEPLOY_DIR"
cd "$DEPLOY_DIR"
[ -f .env ] || bash scripts/odoo20/init-env.sh
docker compose build odoo
bash scripts/odoo20/install-modules.sh
docker compose up -d
port="$(grep ^HTTP_PORT .env | cut -d= -f2)"
for i in $(seq 1 60); do
  code="$(curl -s -o /dev/null -w '%{http_code}' -m 5 "http://127.0.0.1:${port:-18080}/web/login" || true)"; [ "$code" = 200 ] && break; sleep 5
done
echo "Odoo 20 en 127.0.0.1:${port:-18080}/web/login -> HTTP $code"
[ "$code" = 200 ] || { docker compose logs --tail 30 odoo; exit 1; }
