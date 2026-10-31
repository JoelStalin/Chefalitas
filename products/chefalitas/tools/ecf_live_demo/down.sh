#!/usr/bin/env bash
# Removes the live e-CF demo (containers and volumes). COMPOSE_PROJECT_NAME=ecfcert ./down.sh removes the real-DGII one.
: "${COMPOSE_PROJECT_NAME:=ecflive}"
cd "$(dirname "$0")" && CHEFALITAS_ADDONS=/tmp ODOO_API_TOKENS=x COMPOSE_PROJECT_NAME=$COMPOSE_PROJECT_NAME docker compose down -v && rm -rf ".state-$COMPOSE_PROJECT_NAME"
