#!/usr/bin/env bash
# Activa los hooks de git del repo (una vez por clon): bash scripts/guard/install-hooks.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
git config core.hooksPath .githooks
chmod +x .githooks/* scripts/guard/*.sh
echo "hooks activados (core.hooksPath=.githooks)"
