#!/usr/bin/env bash
# Crea la base `chefalitas` e instala los modulos de modules.txt (sin datos de demostracion).
# Si la base ya existe, instala los modulos nuevos antes de actualizar los existentes.
set -euo pipefail
cd "$(dirname "$0")/../.."
MODS="$(grep -v '^\s*#' modules.txt | grep -v '^\s*$' | paste -sd, -)"
echo "Modulos: $MODS"
docker compose up -d --wait db
exists="$(docker compose exec -T db psql -U odoo -d postgres -Atc "select 1 from pg_database where datname='chefalitas'" || true)"
PW="$(grep ^POSTGRES_PASSWORD .env | cut -d= -f2)"
run_modules() {
  docker compose run --rm -T odoo odoo -d chefalitas "$1" "$MODS" --without-demo=all --stop-after-init \
    --db_host=db --db_user=odoo --db_password="$PW" --no-database-list 2>&1 | tail -25
}
run_modules -i
[ "$exists" = 1 ] && run_modules -u
bash scripts/odoo20/trim-modules.sh
docker compose exec -T db psql -U odoo -d chefalitas -Atc "update ir_ui_menu set active=false where id in (select res_id from ir_model_data where module='mail' and name='menu_root_discuss')" || true
echo "listo"
