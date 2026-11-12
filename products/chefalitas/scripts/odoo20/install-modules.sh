#!/usr/bin/env bash
# Crea la base `chefalitas` e instala SOLO los modulos de modules.txt (sin datos de demostracion); si ya existe, los actualiza (-u) e instala los nuevos (-i).
set -euo pipefail
cd "$(dirname "$0")/../.."
MODS="$(grep -v '^\s*#' modules.txt | grep -v '^\s*$' | paste -sd, -)"
echo "Modulos: $MODS"
docker compose up -d --wait db
exists="$(docker compose exec -T db psql -U odoo -d postgres -Atc "select 1 from pg_database where datname='chefalitas'" || true)"

if [ "$exists" != 1 ]; then
  docker compose run --rm -T odoo odoo -d chefalitas -i "$MODS" --without-demo=all --stop-after-init     --db_host=db --db_user=odoo --db_password="$(grep ^POSTGRES_PASSWORD .env | cut -d= -f2)" --no-database-list 2>&1 | tail -25
else
  # Detecta modulos pedidos que aun no estan instalados en la base de datos
  uninstalled="$(docker compose exec -T db psql -U odoo -d chefalitas -Atc "
    SELECT string_agg(m, ',') FROM unnest(string_to_array('$MODS', ',')) AS m
    WHERE m NOT IN (SELECT name FROM ir_module_module WHERE state = 'installed');" 2>/dev/null || true)"
  
  if [ -n "$uninstalled" ]; then
    echo "Instalando modulos nuevos pedidos: $uninstalled"
    docker compose run --rm -T odoo odoo -d chefalitas -i "$uninstalled" -u "$MODS" --without-demo=all --stop-after-init       --db_host=db --db_user=odoo --db_password="$(grep ^POSTGRES_PASSWORD .env | cut -d= -f2)" --no-database-list 2>&1 | tail -25
  else
    docker compose run --rm -T odoo odoo -d chefalitas -u "$MODS" --without-demo=all --stop-after-init       --db_host=db --db_user=odoo --db_password="$(grep ^POSTGRES_PASSWORD .env | cut -d= -f2)" --no-database-list 2>&1 | tail -25
  fi
fi

bash scripts/odoo20/trim-modules.sh
docker compose exec -T db psql -U odoo -d chefalitas -Atc "update ir_ui_menu set active=false where id in (select res_id from ir_model_data where module='mail' and name='menu_root_discuss')" || true

# Configura y conecta EasyCount en la empresa principal de Chefalitas
docker compose exec -T db psql -U odoo -d chefalitas -c "
  UPDATE res_company SET
    l10n_do_easycount_enabled = true,
    l10n_do_easycount_url = 'https://easycount.me',
    l10n_do_easycount_token = 'gtu_tnt_ZC1dXKLuJfE0ASnkfcK89yVM1kp044pnZWQaY2Ablws',
    l10n_do_easycount_is_connected = true,
    l10n_do_easycount_is_blocked = false,
    l10n_do_ecf_service_env = 'eCF';
  UPDATE res_partner SET l10n_do_ecf_enabled = true WHERE id IN (SELECT partner_id FROM res_company);
" || true

echo "listo"
