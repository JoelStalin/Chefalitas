# Chefalitas: Odoo 18 → Odoo 20

Decision (2026-10-08): fresh Odoo 20 database plus import. Production is never touched; the source is a read-only
copy restored from `chefalitas_backups/live_from_prod_20261005_192957`.

## Run

```bash
# source: production copy in its own Postgres (read-only for the tool)
docker exec -i chefmig-src-pg pg_restore -U odoo -d chefalitas_src --no-owner --no-acl < chefalitas_live_custom.dump
# target: Odoo 20 with the Chefalitas modules, Dominican chart loaded (company country DO, chart "do")
docker exec -e SRC_DSN="host=chefmig-src-pg dbname=chefalitas_src user=odoo password=..." \
  -e PHASES=master,variants,accounts,moves,reconcile,hr,pos_setup,pos_sessions,pos_orders \
  ecfcert-odoo-1 sh -c "odoo shell -d chef20 --no-http < import18.py"
./validate.sh   # exit 0 = identical to production on every check
```

Phases are idempotent (`__import18__.<table>_<id>` external ids): rerun after a failure and it resumes.
EasyCount e-CF sending stays disabled on the company during the import (history was already reported to DGII).

## Result on chef20 (validated against production)

| Check | Result |
| --- | --- |
| Journal entries | 2,482 / 2,482, same names, states, types, dates and totals |
| Trial balance | identical on all 11 accounts used |
| Customer invoices | 131, RD$ 2,553,368.88, NCF kept (B01/B02/B04) |
| Reconciliations | 1,258 partial / 1,177 full |
| POS | 9,207 orders, 14,310 lines, 10,680 payments, 623 sessions; totals identical |
| Master data | 60 contacts, 447 templates + variants, 2 combos, 3 floors, 39 tables, 8 employees |

## Not imported, on purpose

- **Stock**: every warehouse quant in production is negative (-13,187 units: POS sales with no receipts).
  Opening stock must come from a physical count in Odoo 20 before going live.
- **Floor plan geometry**: Odoo 20 tables have no position/shape fields; redraw the plan in the POS.
- Fields that no longer exist in Odoo 20 are listed per model in the run report (`dropped_fields`).
- Applications installed in production but with no data (sale, purchase, crm, website, mrp, ...) are not installed;
  add them later if needed.
