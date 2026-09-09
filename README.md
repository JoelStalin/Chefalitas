# Chefalitas

Chefalitas is a GetUpSoft B2B SaaS product built on Odoo, PostgreSQL 16, Nginx, and Cloudflare Tunnel.

`local_printer_agent` is an internal component of the Chefalitas POS printing suite. Chefalitas must not be classified as a child of that agent.

## Services
- **Odoo**: Production Odoo container with custom Dominican Republic accounting dependencies (\`pycountry\`, \`phonenumbers\`).
- **PostgreSQL 16**: High-performance tuned database engine.
- **Nginx**: Reverse proxy with Gzip compression, WebSocket support, and Cloudflare header forwarding.
- **Cloudflare Tunnel**: Zero Trust secure edge routing to \`chefalitas.com.do\`.

## Environments

- **Production:** dedicated host; it must remain independent from developer workstations.
- **QA/local:** `DESKTOP-KLAU9I8`; stopped by default and started only for explicit testing.

See `docs/DEPLOYMENT_ENVIRONMENTS.md` for the operating policy and commands.

## Production deploy
\`\`\`bash
docker compose up -d
\`\`\`
