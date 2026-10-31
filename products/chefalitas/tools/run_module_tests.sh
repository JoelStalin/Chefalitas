#!/usr/bin/env bash
# Install <module> in a throwaway Odoo 20 DB and run its tests; prints totals and failures grouped by cause.
m=${1:-whatsapp}; db=t_${m}_$$
docker run --rm --network ecfcert_default -e HOST=odoo-db -e USER=odoo -e PASSWORD=odoo \
  -v ~/workspaces/chefalitas/addons:/mnt/extra-addons:ro \
  chefalitas-odoo20:test odoo --addons-path=/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons \
  -d $db -i $m --without-demo --test-tags /$m --stop-after-init > /tmp/t_$m.log 2>&1
docker exec ecfcert-odoo-db-1 dropdb -U odoo --if-exists $db >/dev/null 2>&1
grep -E "of [0-9]+ tests when loading" /tmp/t_$m.log | tail -1 | sed -E "s/.*(ERROR|INFO) [^:]+: //"
grep -E "^[A-Za-z_.]*(Error|Exception): |^AssertionError" /tmp/t_$m.log | sed -E "s/[0-9]+/N/g" | cut -c1-160 | sort | uniq -c | sort -rn | head -${2:-15}
