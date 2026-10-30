# Chefalitas

Chefalitas is a GetUpSoft B2B SaaS product built on Odoo, PostgreSQL 16, Nginx, and Cloudflare Tunnel.

`local_printer_agent` is an internal component of the Chefalitas POS printing suite. Chefalitas must not be classified as a child of that agent.

## Services
- **Odoo 20**: contenedor de produccion con las dependencias de contabilidad dominicana (`pycountry`, `phonenumbers`). Version del repositorio: 20.0.0 (archivo `VERSION`).
- **PostgreSQL 16**: High-performance tuned database engine.
- **Nginx**: Reverse proxy with Gzip compression, WebSocket support, and Cloudflare header forwarding.
- **Cloudflare Tunnel**: Zero Trust secure edge routing to \`chefalitas.com.do\`.

## Environments

- **Production:** dedicated host; it must remain independent from developer workstations.
- **QA/local:** `DESKTOP-KLAU9I8`; stopped by default and started only for explicit testing.

See `docs/DEPLOYMENT_ENVIRONMENTS.md` for the operating policy and commands.

## Produccion (Odoo 20)
Chefalitas corre en Odoo 20, conectado a EasyCount (EasyCount es el bus con la DGII: Odoo no habla con la DGII).

- Modulos instalados: `modules.txt` (facturacion, inventario, localizacion dominicana, POS, cocina, fripick, impresoras, nomina y empleados, balanza,
  `orca_bridge` e IA conectada a ORCA). No se instala Discuss.
- Despliegue: solo por GitHub Actions, en el runner propio del servidor de produccion (`.github/workflows/deploy-prod-odoo20.yml`, al publicar una
  version `v20.*` o a mano). Local o ensayo: `bash scripts/odoo20/init-env.sh && docker compose build odoo && bash scripts/odoo20/install-modules.sh && docker compose up -d`.
- Odoo 18 y 19 quedan como legado (`Dockerfile.odoo18`, `Dockerfile.odoo19`, `deploy-odoo18-legacy.yml`).
- Plan de cambio y reversa: `docs/ODOO20_PRODUCCION.md`.
