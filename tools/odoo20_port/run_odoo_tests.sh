#!/usr/bin/env bash
# Throwaway Odoo test run for Chefalitas addons (Etapa 1). Isolated network/DB, prefix etapa1-.
# Mounts the whole Chefalitas addons dir (orca_addons is gitignored and not in this clone).
# Usage: run_odoo_tests_etapa1.sh [odoo_image] [test_tags] [modules_to_install(comma list)]
set -u
IMAGE="${1:-odoo:20.0}"
TAGS="${2:-/l10n_do_accounting}"
MODS="${3:-l10n_do_accounting}"
ADDONS=/home/ubuntu/workspaces/chefalitas/addons
LOG=/home/ubuntu/etapa1-odoo-tests-$(date +%Y%m%d-%H%M%S).log

docker pull -q "$IMAGE" >/dev/null
docker network inspect etapa1-net >/dev/null 2>&1 || docker network create etapa1-net >/dev/null
docker rm -f etapa1-db >/dev/null 2>&1
docker run -d --name etapa1-db --network etapa1-net \
  -e POSTGRES_USER=odoo -e POSTGRES_PASSWORD=odoo -e POSTGRES_DB=postgres postgres:16-alpine >/dev/null
for i in $(seq 1 30); do docker exec etapa1-db pg_isready -U odoo >/dev/null 2>&1 && break; sleep 2; done

docker run --rm --shm-size=1g --network etapa1-net -e HOST=etapa1-db -e USER=odoo -e PASSWORD=odoo \
  -v "$ADDONS":/mnt/extra-addons:ro \
  "$IMAGE" odoo \
  -d etapa1_test -i "$MODS" --test-tags "$TAGS" \
  --stop-after-init --log-level=test --without-demo=all > "$LOG" 2>&1
RC=$?

docker rm -f etapa1-db >/dev/null 2>&1
docker network rm etapa1-net >/dev/null 2>&1
echo "exit=$RC log=$LOG"
grep -E "ERROR|FAIL|Ran [0-9]+ tests|failed|odoo.tests.stats|ParseError|Traceback" "$LOG" | tail -40
