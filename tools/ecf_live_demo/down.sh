#!/usr/bin/env bash
# Removes the live e-CF demo (containers and volumes).
cd "$(dirname "$0")" && CHEFALITAS_ADDONS=/tmp ODOO_API_TOKENS=x docker compose down -v && rm -rf .state
