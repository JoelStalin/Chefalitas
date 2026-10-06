#!/usr/bin/env bash
# Starts the live e-CF demo: Odoo 20 http://127.0.0.1:18069 (admin/admin), EasyCount http://127.0.0.1:18800.
# Usage: CHEFALITAS_ADDONS=/path/to/addons EASYCOUNT_REPO=/path/to/EasyCount ./up.sh   (./down.sh removes it)
set -euo pipefail
cd "$(dirname "$0")"
: "${CHEFALITAS_ADDONS:=$(cd ../../addons && pwd)}"
: "${EASYCOUNT_REPO:?path to the EasyCount repository (apps/api-nest, alembic)}"
: "${EASYCOUNT_VENV:=/home/ubuntu/venvs/easycount-etapa1}"
export CHEFALITAS_ADDONS
STATE=.state; mkdir -p "$STATE"; chmod 700 "$STATE"
[ -s "$STATE/token" ] || openssl rand -hex 24 > "$STATE/token"
TOKEN=$(cat "$STATE/token")
export ODOO_API_TOKENS="131793916=$TOKEN"

echo "== EasyCount NestJS image"
docker build -q -t easycount-api-nest:live "$EASYCOUNT_REPO/apps/api-nest" >/dev/null
docker compose up -d odoo-db easycount-db
for i in $(seq 1 30); do docker compose exec -T easycount-db pg_isready -h 127.0.0.1 -U ec >/dev/null 2>&1 && break; sleep 2; done

echo "== EasyCount schema (alembic) + tenant"
EC_IP=$(docker inspect ecflive-easycount-db-1 -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
( cd "$EASYCOUNT_REPO" && STORAGE_BASE_PATH=/tmp/ecflive/storage PSC_WORKFLOW_STORAGE_PATH=/tmp/ecflive/psc \
  DATABASE_URL="postgresql+psycopg://ec:ec@$EC_IP:5432/easycount" "$EASYCOUNT_VENV/bin/alembic" upgrade head >/dev/null )
docker compose exec -T easycount-db psql -q -U ec -d easycount -c \
  "INSERT INTO tenants (created_at, updated_at, name, rnc) VALUES (now(), now(), 'Chefalitas (PRUEBAS e-CF)', '131793916') ON CONFLICT (rnc) DO NOTHING"
docker compose up -d easycount

echo "== Odoo 20: modules"
if ! docker compose exec -T odoo-db psql -U odoo -lqt 2>/dev/null | cut -d'|' -f1 | grep -qw ecflive; then
  docker compose run --rm -T odoo odoo -d ecflive --without-demo=all --stop-after-init --log-level=warn \
    -i l10n_do_accounting,l10n_do_accounting_report,pos_l10n_do_restaurant,pos_system,purchase,sale_management 2>&1 | grep -E "ERROR|CRITICAL" | head -5 || true
fi
echo "== Odoo 20: demo data"
docker compose run --rm -T -e EASYCOUNT_TOKEN="$TOKEN" odoo odoo shell -d ecflive --no-http --log-level=warn \
  < setup_odoo.py 2>&1 | grep -E "POS:|taxes:|SETUP|Error|Traceback" || true
docker compose up -d odoo
for i in $(seq 1 60); do curl -sf -o /dev/null http://127.0.0.1:18069/web/login && break; sleep 2; done
echo "Odoo: http://127.0.0.1:18069 (admin/admin)  EasyCount: http://127.0.0.1:18800/healthz"
