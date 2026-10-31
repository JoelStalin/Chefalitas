#!/usr/bin/env bash
# Crea la base `chefalitas` e instala SOLO los modulos de modules.txt (sin datos de demostracion); si ya existe, los actualiza (-u).
set -euo pipefail
cd "$(dirname "$0")/../.."
MODS="$(grep -v '^\s*#' modules.txt | grep -v '^\s*$' | paste -sd, -)"
echo "Modulos: $MODS"
docker compose up -d --wait db
exists="$(docker compose exec -T db psql -U odoo -d postgres -Atc "select 1 from pg_database where datname='chefalitas'" || true)"
flag='-i'; [ "$exists" = 1 ] && flag='-u'
docker compose run --rm -T odoo odoo -d chefalitas $flag "$MODS" --without-demo=all --stop-after-init \
  --db_host=db --db_user=odoo --db_password="$(grep ^POSTGRES_PASSWORD .env | cut -d= -f2)" --no-database-list 2>&1 | tail -25
bash scripts/odoo20/trim-modules.sh
docker compose exec -T db psql -U odoo -d chefalitas -Atc "update ir_ui_menu set active=false where id in (select res_id from ir_model_data where module='mail' and name='menu_root_discuss')" || true
echo "listo"
