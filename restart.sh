#!/usr/bin/env bash
set -e

echo ">> Bajando contenedores..."
docker compose down

echo ">> Levantando contenedores en segundo plano..."
docker compose up -d

echo ">> Instalando dependencias en /mnt/extra-addons dentro del contenedor odoo18-odoo-1..."
docker exec -u root odoo18-odoo-1 bash -c "
  cd /mnt/extra-addons && \
  pip3 install --break-system-packages -r requirements.txt
"

echo ">> Reiniciando servicios de Docker Compose..."
docker compose restart

echo '>> Todo OK ✅'
