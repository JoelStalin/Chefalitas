#!/usr/bin/env bash
# Before merging the commit that stops tracking .env (c478dd1) into main: copy the production
# .env out of the git working tree so the next pull does not delete it.
# Usage: PROD=chefalitas_pro APP_DIR=/path/to/chefalitas ./backup_prod_env.sh
# Copies the file on the server itself; the value never leaves the server.
set -euo pipefail
: "${PROD:=chefalitas_pro}"; : "${APP_DIR:?path of the Chefalitas checkout on the server}"
ssh "$PROD" "set -e; cd '$APP_DIR'; test -f .env; mkdir -p ~/env-backups; chmod 700 ~/env-backups;   cp -p .env ~/env-backups/chefalitas.env.\20261007-004302; chmod 600 ~/env-backups/*; ls -l ~/env-backups | tail -3"
echo 'After the deploy: if .env was removed, restore it from ~/env-backups on the server.'
