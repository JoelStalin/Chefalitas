#!/usr/bin/env bash
set -euo pipefail

COMPOSE="docker compose"
ODOO_SERVICE="${ODOO_SERVICE:-odoo}"

echo ">> Construyendo imagen de Odoo (si aplica)..."
$COMPOSE build "$ODOO_SERVICE"

echo ">> Levantando/actualizando solo el servicio de Odoo (sin tocar la DB)..."
$COMPOSE up -d --no-deps "$ODOO_SERVICE"

echo ">> Dependencias: instaladas en build (skipping runtime pip install)."

echo ">> Reiniciando solo Odoo para aplicar cambios..."
$COMPOSE restart "$ODOO_SERVICE"

echo ">> Todo OK."
