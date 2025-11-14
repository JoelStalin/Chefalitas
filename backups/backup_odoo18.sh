#!/usr/bin/env bash
set -euo pipefail

# === CONFIGURACIÓN ===

# Directorio donde está el script (carpeta "backups")
BACKUP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DB_VOLUME="odoo18_db-data"        # Volumen de PostgreSQL
ODOO_VOLUME="odoo18_odoo-data"    # Volumen de datos de Odoo (filestore, etc.)

# Contenedor de PostgreSQL (ajusta si tu docker ps muestra otro nombre)
PG_CONTAINER="odoo18-db-1"
# Usuario superusuario de PostgreSQL (según tu .env)
PG_USER="odoo"

TIMESTAMP="$(date +%F_%H-%M-%S)"

mkdir -p "$BACKUP_DIR"

echo "➡ Usando carpeta de backups: $BACKUP_DIR"

echo "➡ Eliminando backups anteriores..."
# Borrar solo archivos que empiecen por odoo18_
if compgen -G "$BACKUP_DIR/odoo18_*.tgz" > /dev/null; then
  rm -f "$BACKUP_DIR"/odoo18_*.tgz
  echo "✅ Backups .tgz anteriores eliminados."
else
  echo "ℹ️ No se encontraron backups .tgz anteriores."
fi

# Borrar backups lógicos previos (pg_dump)
if compgen -G "$BACKUP_DIR/odoo18_pg_*.sql.gz" > /dev/null; then
  rm -f "$BACKUP_DIR"/odoo18_pg_*.sql.gz
  echo "✅ Backups pg_dump anteriores eliminados."
else
  echo "ℹ️ No se encontraron backups pg_dump anteriores."
fi

echo "➡ Verificando que los volúmenes existan..."
for v in "$DB_VOLUME" "$ODOO_VOLUME"; do
  if ! docker volume inspect "$v" &>/dev/null; then
    echo "❌ ERROR: El volumen '$v' no existe."
    exit 1
  fi
done

echo "➡ Creando backup de la BASE DE DATOS (volumen: $DB_VOLUME)..."
docker run --rm \
  -v "${DB_VOLUME}":/data:ro \
  -v "${BACKUP_DIR}":/backup \
  ubuntu \
  tar czf "/backup/odoo18_db_${TIMESTAMP}.tgz" /data

echo "➡ Creando backup de los FILES de Odoo (volumen: $ODOO_VOLUME)..."
docker run --rm \
  -v "${ODOO_VOLUME}":/data:ro \
  -v "${BACKUP_DIR}":/backup \
  ubuntu \
  tar czf "/backup/odoo18_odoo_${TIMESTAMP}.tgz" /data

echo "➡ Creando backup LÓGICO de PostgreSQL con pg_dumpall..."
docker exec "$PG_CONTAINER" \
  pg_dumpall -U "$PG_USER" \
  | gzip > "$BACKUP_DIR/odoo18_pg_${TIMESTAMP}.sql.gz"

echo "✅ Backups creados en: $BACKUP_DIR"
ls -lh "$BACKUP_DIR"/odoo18_*"${TIMESTAMP}".tgz "$BACKUP_DIR"/odoo18_pg_"${TIMESTAMP}".sql.gz 2>/dev/null || true

# Ejemplo de uso:
# cd ~/odoo18/backups
# chmod +x backup_odoo18.sh
# ./backup_odoo18.sh
