# Chefalitas Odoo 20 en produccion: cambio y reversa

## Que cambia
- Version 20.0.0 del repositorio: `Dockerfile` y `docker-compose.yml` son de Odoo 20; los modulos propios estan todos en version 20.0
  (se incorporaron `l10n_do_hr_payroll`, `ai_provider` y `pos_scale_gateway`, de GetUpSoft, LGPL-3).
- Solo se migran la compania y los clientes (`res.company`, `res.partner`) desde la base viva de Odoo 19. Los comprobantes se emiten desde EasyCount
  (el bus con la DGII) y quedan guardados alli; los reportes DGII salen de EasyCount.
- El dominio no cambia para la DGII: las URL registradas apuntan a EasyCount, no a chefalitas.com.do.

## Cambio de dominio
1. Respaldo completo de la produccion actual (Odoo 19) y de su base `chefalitas`.
2. Odoo 20 corriendo y probado en 127.0.0.1:18080 (nginx) del mismo servidor, sin tocar la produccion actual.
3. Cloudflare Tunnel: `old.chefalitas.com.do` -> la version vieja (127.0.0.1:18069); `chefalitas.com.do` y `www.chefalitas.com.do` -> Odoo 20 (127.0.0.1:18080).
4. Verificar login, un cliente, un comprobante de prueba por EasyCount.

## Reversa
- Devolver `chefalitas.com.do` y `www.chefalitas.com.do` a 127.0.0.1:18069 en el tunel; la version vieja sigue intacta con su base.
- Odoo 20 se detiene con `docker compose down` (sin `-v` conserva los datos).
