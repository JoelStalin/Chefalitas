# Chefalitas Production Infrastructure

Production environment for Chefalitas with Odoo, PostgreSQL 16, Nginx, and Cloudflare Tunnel.

## Services
- **Odoo**: Production Odoo container with custom Dominican Republic accounting dependencies (\`pycountry\`, \`phonenumbers\`).
- **PostgreSQL 16**: High-performance tuned database engine.
- **Nginx**: Reverse proxy with Gzip compression, WebSocket support, and Cloudflare header forwarding.
- **Cloudflare Tunnel**: Zero Trust secure edge routing to \`chefalitas.com.do\`.

## Deploy
\`\`\`bash
docker compose up -d
\`\`\`
