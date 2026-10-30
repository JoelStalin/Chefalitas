#!/usr/bin/env bash
# Crea .env con una clave aleatoria (solo si no existe). No se versiona.
set -euo pipefail
cd "$(dirname "$0")/../.."
[ -f .env ] && { echo ".env ya existe"; exit 0; }
umask 077
{ echo "POSTGRES_PASSWORD=$(openssl rand -base64 36 | tr -d '/+=\n' | cut -c1-28)"; echo "HTTP_PORT=${HTTP_PORT:-18080}"; } > .env
chmod 600 .env
echo ".env creado (600)"
