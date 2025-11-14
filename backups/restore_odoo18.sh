#!/usr/bin/env bash
set -euo pipefail

# === RUTAS BASE ===

# Carpeta donde está el script (en tu caso: /home/ubuntu/odoo18/backups)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Carpeta de backups = la misma donde está el script
BACKUP_DIR="$SCRIPT_DIR"

# Carpeta del proyecto = padre de backups (en tu caso: /home/ubuntu/odoo18)
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

DB_VOLUME="odoo18_db-data"
ODOO_VOLUME="odoo18_odoo-data"

# Contenedor de PostgreSQL y usuario (según tu .env y docker)
PG_CONTAINER="odoo18-db-1"   # <-- AJUSTA este nombre según tu docker ps
PG_USER="odoo"               # de tu .env (POSTGRES_USER)
PG_DB="postgres"             # DB a la que nos conectamos para aplicar el dump

# Detectar si usas docker compose plugin o docker-compose clásico
if command -v docker-compose &>/dev/null; then
  COMPOSE="docker-compose"
else
  COMPOSE="docker compose"
fi

echo "➡ BACKUP_DIR:  $BACKUP_DIR"
echo "➡ PROJECT_DIR: $PROJECT_DIR"

echo "➡ Buscando el último backup disponible en: $BACKUP_DIR"

# Obtener el backup de DB más reciente (para extraer TIMESTAMP)
DB_BACKUP="$(ls -1t "$BACKUP_DIR"/odoo18_db_*.tgz 2>/dev/null | head -n 1 || true)"

if [[ -z "$DB_BACKUP" ]]; then
  echo "❌ No se encontró ningún backup de base de datos (odoo18_db_*.tgz) en $BACKUP_DIR"
  exit 1
fi

DB_BASENAME="$(basename "$DB_BACKUP")"
# de: odoo18_db_2025-11-13_12-34-56.tgz
# a:  2025-11-13_12-34-56
TIMESTAMP="${DB_BASENAME#odoo18_db_}"
TIMESTAMP="${TIMESTAMP%.tgz}"

ODOO_BACKUP="$BACKUP_DIR/odoo18_odoo_${TIMESTAMP}.tgz"
PG_BACKUP="$BACKUP_DIR/odoo18_pg_${TIMESTAMP}.sql.gz"

echo "➡ Usando TIMESTAMP detectado: $TIMESTAMP"
echo "   - DB (volumen, NO se usará): $DB_BACKUP"
echo "   - FILES:                      $ODOO_BACKUP"
echo "   - PG_DUMP:                    $PG_BACKUP"

echo "➡ Verificando archivos de backup..."
if [ ! -f "$ODOO_BACKUP" ]; then
  echo "❌ No se encontró el backup de files: $ODOO_BACKUP"
  exit 1
fi

if [ ! -f "$PG_BACKUP" ]; then
  echo "❌ No se encontró el backup lógico de Postgres: $PG_BACKUP"
  exit 1
fi

echo "➡ Apagando el stack de Docker..."
cd "$PROJECT_DIR"
$COMPOSE down

echo "➡ Limpiando volumen de BASE DE DATOS ($DB_VOLUME)..."
docker run --rm \
  -v "${DB_VOLUME}":/data \
  ubuntu \
  bash -c "cd /data && rm -rf ./*"

echo "➡ Restaurando FILES de Odoo desde $ODOO_BACKUP ..."
docker run --rm \
  -v "${ODOO_VOLUME}":/data \
  -v "${BACKUP_DIR}":/backup \
  ubuntu \
  bash -c "cd /data && rm -rf ./* && tar xzf /backup/$(basename "$ODOO_BACKUP") --strip 1"

echo "➡ Levantando el stack de Docker (para tener PostgreSQL levantado)..."
cd "$PROJECT_DIR"
$COMPOSE up -d

echo "➡ Esperando que PostgreSQL esté disponible..."
# Esperar hasta 60s a que esté arriba
for i in {1..30}; do
  if docker exec "$PG_CONTAINER" pg_isready -U "$PG_USER" >/dev/null 2>&1; then
    echo "✅ PostgreSQL está listo."
    break
  fi
  sleep 2
done

# Restaurar la base de datos desde el backup lógico
echo "➡ Restaurando BASE DE DATOS desde backup lógico $PG_BACKUP ..."
gunzip -c "$PG_BACKUP" \
  | docker exec -i "$PG_CONTAINER" psql -U "$PG_USER" "$PG_DB"

echo "✅ Restauración completada con el backup: $TIMESTAMP"

# Ejemplo de uso:
# cd ~/odoo18/backups
# chmod +x restore_odoo18.sh
# ./restore_odoo18.sh
