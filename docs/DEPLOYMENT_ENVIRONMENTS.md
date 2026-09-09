# Chefalitas deployment environments

## Product ownership

Chefalitas is a GetUpSoft B2B SaaS product. The local printer agent belongs to `addons/pos_printing_suite/agent_src/local_printer_agent`; it is not the parent application.

## Production

Production must run on its dedicated host with PostgreSQL, filestore, addons, Nginx, and Cloudflare Tunnel kept together and backed up. A developer workstation must not be the long-term public origin.

Do not stop the current origin or move the public tunnel until the replacement host passes database, filestore, assets, login, scheduled-job, restart, and public-hostname checks.

## QA on DESKTOP-KLAU9I8

The Chefalitas stack on `DESKTOP-KLAU9I8` is QA-only. It stays stopped unless an explicit test session requires it.

Start QA:

```bash
docker compose -f docker-compose.yml -f compose.qa.yml --profile qa up -d
```

Stop QA after evidence is collected:

```bash
docker compose -f docker-compose.yml -f compose.qa.yml --profile qa down
```

The QA override disables automatic container restart. Never attach the production Cloudflare hostname to this QA stack after production cutover.
