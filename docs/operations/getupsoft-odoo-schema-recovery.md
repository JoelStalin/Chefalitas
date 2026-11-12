# GetUpSoft Odoo schema recovery

Backlog: TASK-ODOO-GETUPSOFT-AVAILABILITY-20261112.

## DoR

- Public `/web/login` times out while TLS succeeds.
- `getupsoft-odoo20-odoo-1` and database container are running.
- Logs show `UndefinedColumn: res_company.l10n_do_easycount_is_blocked`.
- Database module version is `20.0.1.1.1`; mounted code declares the field.
- Review and merge this workflow into `main`; configure a required reviewer on GitHub environment `getupsoft-odoo-production`.

## Execution

Dispatch `Recover GetUpSoft Odoo schema` from `main` with `target=getupsoft` and `modules=l10n_do_accounting`. The job checks environment protection, backs up the GetUpSoft database and filestore to `/home/ubuntu/deploy-backups/getupsoft-odoo20/<UTC>-<SHA>/`, verifies archive readability and SHA256 checksums, fast-forwards the clean checkout to the dispatched SHA, upgrades only `l10n_do_accounting` in database `getupsoft`, restarts only `getupsoft-odoo20-odoo-1`, and verifies the local and public login. It does not target `ecflive` or any tunnel.

## DoD

- Workflow succeeded with its approved production environment.
- Backup path and deployment SHA appear in the run log.
- New column exists; local and public `/web/login` return HTTP 200.
- No recurrence of the missing-column error after restart.
- Browser login and relevant billing flow are checked before claiming service fully restored.

## Rollback

Stop and investigate if upgrade or health checks fail. Preserve the backup and logs. A rollback would require a separately reviewed GitHub Actions recovery workflow to restore the verified dump and filestore together, then deploy the recorded `previous-sha.txt`; never restore the database alone while running newer code. Do not run direct host SQL, restart, or tunnel changes.

Risk: the `main` delta includes module version `20.0.1.1.2` and its ORM migration, which recalculates signed e-CF QR fields on historical invoices. Review its impact and backup before approving the environment.
