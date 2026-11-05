#!/usr/bin/env bash
# Migra compañías, contactos y usuarios del Odoo 18 de producción al Odoo 20 (lo ejecuta migrate-odoo18-to-20.yml en el runner de producción).
# 1) Respalda la base Odoo 18 completa. 2) Exporta los datos a JSON. 3) Los importa en Odoo 20 con el ORM (sin duplicar).
# Variables: OLD_DB_CONTAINER (chefalitas-db-prod), OLD_DB (se detecta si hay una sola base), DEPLOY_DIR (Odoo 20), DRY_RUN=1 solo informa.
set -euo pipefail
OLD_DB_CONTAINER="${OLD_DB_CONTAINER:-chefalitas-db-prod}"
DEPLOY_DIR="${DEPLOY_DIR:-/home/yoeli/chefalitas-odoo20}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/chefalitas-backups}"
SRC="$(cd "$(dirname "$0")/../.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

PGUSER_OLD="$(docker exec "$OLD_DB_CONTAINER" printenv POSTGRES_USER || echo odoo)"
psql_old() { docker exec -i "$OLD_DB_CONTAINER" psql -U "$PGUSER_OLD" -v ON_ERROR_STOP=1 "$@"; }

if [ -z "${OLD_DB:-}" ]; then
  mapfile -t dbs < <(psql_old -d postgres -Atc "select datname from pg_database where not datistemplate and datname <> 'postgres'")
  echo "Bases en Odoo 18: ${dbs[*]}"
  [ "${#dbs[@]}" -eq 1 ] || { echo "Hay ${#dbs[@]} bases; defina OLD_DB"; exit 1; }
  OLD_DB="${dbs[0]}"
fi
echo "Base de origen: $OLD_DB"

echo "== 1/3 Respaldo completo de $OLD_DB"
docker exec "$OLD_DB_CONTAINER" pg_dump -U "$PGUSER_OLD" -Fc "$OLD_DB" > "$BACKUP_DIR/odoo18-$OLD_DB-$STAMP.dump"
[ -s "$BACKUP_DIR/odoo18-$OLD_DB-$STAMP.dump" ] || { echo "El respaldo quedó vacío; no sigo"; exit 1; }
ls -la "$BACKUP_DIR/odoo18-$OLD_DB-$STAMP.dump"

echo "== 2/3 Exportar compañías, contactos y usuarios"
OUT="$BACKUP_DIR/odoo18-export-$STAMP.json"
psql_old -d "$OLD_DB" -At -f - > "$OUT" < "$SRC/scripts/odoo20/migrate_export_18.sql"
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print({k: len(v or []) for k, v in d.items()})" "$OUT"
chmod 600 "$OUT"   # contiene las claves cifradas de los usuarios

if [ "${DRY_RUN:-0}" = 1 ]; then echo "DRY_RUN: no se importa nada"; exit 0; fi

echo "== 3/3 Importar en Odoo 20"
cd "$DEPLOY_DIR"
docker compose cp "$OUT" odoo:/tmp/odoo18-export.json
docker compose cp "$SRC/scripts/odoo20/migrate_import_20.py" odoo:/tmp/migrate_import_20.py
PW="$(grep ^POSTGRES_PASSWORD .env | cut -d= -f2)"
docker compose exec -T odoo sh -c "odoo shell -d chefalitas --db_host=db --db_user=odoo --db_password='$PW' --no-http < /tmp/migrate_import_20.py" 2>&1 | grep -E "^MIGRACION|Traceback|Error" | tail -30
docker compose exec -T odoo rm -f /tmp/odoo18-export.json
echo "Respaldo: $BACKUP_DIR/odoo18-$OLD_DB-$STAMP.dump"
