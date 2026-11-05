#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-$(basename "$SCRIPT_DIR")}"
ODOO_SERVICE="${ODOO_SERVICE:-odoo}"

compose() {
  docker compose -p "$PROJECT_NAME" -f "$SCRIPT_DIR/docker-compose.yml" "$@"
}

echo ">> Construyendo imagen de Odoo (si aplica)..."
compose build "$ODOO_SERVICE"

echo ">> Levantando/actualizando servicios..."
compose up -d

echo ">> Actualizando modulos ORCA y contabilidad/POS en base de datos..."
compose exec -T "$ODOO_SERVICE" odoo -u orca_bridge,l10n_do_accounting,pos_system,pos_kitchen_core -d chefalitas --stop-after-init || true

echo ">> Reiniciando Odoo para cargar nuevas rutas..."
compose restart "$ODOO_SERVICE"

echo ">> Todo OK."
