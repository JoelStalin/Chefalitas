#!/usr/bin/env bash
# Deja instalados SOLO los modulos de modules.txt y sus dependencias obligatorias: desinstala los que Odoo instala solo (auto_install).
# Los del nucleo que no se dejan desinstalar (p. ej. `rpc`) se reportan y se aceptan. Repetible tras cada instalacion/actualizacion.
set -euo pipefail
cd "$(dirname "$0")/../.."
TOP="$(grep -v '^\s*#' modules.txt | grep -v '^\s*$' | paste -sd, -)"
PW="$(grep ^POSTGRES_PASSWORD .env | cut -d= -f2)"
docker compose up -d --wait db
extras() {
  docker compose exec -T db psql -U odoo -d chefalitas -Atc "
    WITH RECURSIVE need(name) AS (
      SELECT unnest(string_to_array('$TOP', ','))
      UNION SELECT d.name FROM need n JOIN ir_module_module m ON m.name = n.name JOIN ir_module_module_dependency d ON d.module_id = m.id)
    SELECT string_agg(name, ',' ORDER BY name) FROM ir_module_module WHERE state = 'installed' AND name NOT IN (SELECT name FROM need)"
}
EX="$(extras)"
[ -z "$EX" ] && { echo "Sin extras: solo modulos pedidos y dependencias obligatorias."; exit 0; }
echo "Extras a desinstalar: $EX"
docker compose run --rm -T -e EX="$EX" odoo odoo shell -d chefalitas --db_host=db --db_user=odoo --db_password="$PW" --no-database-list <<'PY' 2>&1 | tail -14
import os, re, time
from odoo.exceptions import UserError
extras = os.environ['EX'].split(',')
for attempt in range(15):
    mods = env['ir.module.module'].search([('name', 'in', extras), ('state', '=', 'installed')])
    if not mods:
        print('nada mas que desinstalar'); break
    try:
        print('desinstalando', len(mods), 'modulos'); mods.button_immediate_uninstall(); env.cr.commit(); print('hecho'); break
    except UserError as e:
        if 'scheduled action' in str(e):
            # el Odoo que sigue sirviendo ejecuta un cron y Odoo no deja tocar modulos en ese momento: se espera y se reintenta
            env.cr.rollback(); print('Odoo ejecuta una accion programada; reintento en 20 s (intento %d)' % (attempt + 1)); time.sleep(20); continue
        m = re.search(r'cannot be uninstalled: (.+)$', str(e))
        if not m: raise
        skip = [x.strip() for x in m.group(1).split(',')]
        print('nucleo de Odoo, no desinstalable:', skip); env.cr.rollback()
        extras = [x for x in extras if x not in skip]
PY
EX2="$(extras)"
[ -z "$EX2" ] && echo "Sin extras: OK" || echo "Quedan solo modulos del nucleo de Odoo que no se pueden desinstalar: $EX2"
docker compose exec -T db psql -U odoo -d chefalitas -Atc "select count(*)||' modulos instalados' from ir_module_module where state='installed'"
