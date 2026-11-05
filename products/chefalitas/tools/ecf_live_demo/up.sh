#!/usr/bin/env bash
# Starts the live e-CF demo: Odoo 20 http://127.0.0.1:18069 (admin/admin), EasyCount http://127.0.0.1:18800.
# Usage: CHEFALITAS_ADDONS=/path/to/addons EASYCOUNT_REPO=/path/to/EasyCount ./up.sh   (./down.sh removes it)
# Real DGII (certification), separate project and ports so the emulator demo is untouched:
#   COMPOSE_PROJECT_NAME=ecfcert ODOO_PORT=18070 EC_PORT=18801 DGII_ENV=CERT DEMO_RNC=<rnc> DEMO_NAME="<razon social>" \
#   DGII_P12_HOST=/path/cert.p12 DGII_P12_PASSWORD=... DGII_CERT_EXPECTED_RNC=<rnc> DGII_SEQ_EXPIRY=31-12-2028 SEQ_START=1001 ./up.sh
set -euo pipefail
cd "$(dirname "$0")"
: "${CHEFALITAS_ADDONS:=$(cd ../../addons && pwd)}"
: "${EASYCOUNT_REPO:?path to the EasyCount repository (apps/api-nest, alembic)}"
: "${EASYCOUNT_VENV:=/home/ubuntu/venvs/easycount-etapa1}"
: "${COMPOSE_PROJECT_NAME:=ecflive}"
: "${DEMO_RNC:=131793916}"
: "${DEMO_NAME:=Chefalitas (PRUEBAS e-CF)}"
: "${SEQ_START:=1}"  # first e-NCF number per type; numbers already used at the DGII cannot be reused
export CHEFALITAS_ADDONS COMPOSE_PROJECT_NAME DEMO_RNC DEMO_NAME
STATE=.state-$COMPOSE_PROJECT_NAME; mkdir -p "$STATE"; chmod 700 "$STATE"
[ -s "$STATE/token" ] || openssl rand -hex 24 > "$STATE/token"
TOKEN=$(cat "$STATE/token")
export ODOO_API_TOKENS="$DEMO_RNC=$TOKEN"

echo "== EasyCount NestJS image"
docker build -q -t easycount-api-nest:live "$EASYCOUNT_REPO/apps/api-nest" >/dev/null
docker compose up -d odoo-db easycount-db
for i in $(seq 1 30); do docker compose exec -T easycount-db pg_isready -h 127.0.0.1 -U ec >/dev/null 2>&1 && break; sleep 2; done

echo "== EasyCount schema (alembic) + tenant"
EC_IP=$(docker inspect "$(docker compose ps -q easycount-db)" -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
( cd "$EASYCOUNT_REPO" && DGII_ENV=LOCAL STORAGE_BASE_PATH=/tmp/ecflive/storage PSC_WORKFLOW_STORAGE_PATH=/tmp/ecflive/psc \
  DATABASE_URL="postgresql+psycopg://ec:ec@$EC_IP:5432/easycount" "$EASYCOUNT_VENV/bin/alembic" upgrade head >/dev/null )
docker compose exec -T easycount-db psql -q -U ec -d easycount -c \
  "INSERT INTO tenants (created_at, updated_at, name, rnc) VALUES (now(), now(), '$(printf %s "$DEMO_NAME" | sed "s/'/''/g")', '$DEMO_RNC') ON CONFLICT (rnc) DO NOTHING"
if [ "$SEQ_START" -gt 1 ]; then
  docker compose exec -T easycount-db psql -q -U ec -d easycount -c \
    "INSERT INTO sequences (tenant_id, doc_type, prefix, next_number, created_at, updated_at)
     SELECT t.id, d, 'E' || d, $SEQ_START, now(), now() FROM tenants t, unnest(ARRAY['31','32','33','34','41','43','44','45','46','47']) d
     WHERE t.rnc = '$DEMO_RNC' ON CONFLICT DO NOTHING"
fi
docker compose up -d easycount

echo "== Odoo 20: modules"
if ! docker compose exec -T odoo-db psql -U odoo -lqt 2>/dev/null | cut -d'|' -f1 | grep -qw ecflive; then
  docker compose run --rm -T odoo odoo -d ecflive --without-demo=all --stop-after-init --log-level=warn \
    -i l10n_do_accounting,l10n_do_accounting_report,pos_l10n_do_restaurant,pos_system,purchase,sale_management 2>&1 | grep -E "ERROR|CRITICAL" | head -5 || true
fi
echo "== Odoo 20: demo data"
docker compose run --rm -T -e EASYCOUNT_TOKEN="$TOKEN" -e DEMO_RNC -e DEMO_NAME odoo odoo shell -d ecflive --no-http --log-level=warn \
  < setup_odoo.py 2>&1 | grep -E "POS:|taxes:|SETUP|Error|Traceback" || true
docker compose up -d odoo
for i in $(seq 1 60); do curl -sf -o /dev/null "http://127.0.0.1:${ODOO_PORT:-18069}/web/login" && break; sleep 2; done
echo "Odoo: http://127.0.0.1:${ODOO_PORT:-18069} (admin/admin)  EasyCount: http://127.0.0.1:${EC_PORT:-18800}/healthz  DGII: ${DGII_ENV:-LOCAL}"
