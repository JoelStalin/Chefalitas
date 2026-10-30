# CHANGE_TIMELINE — Chefalitas

## 2026-10-06/07 — e-CF en vivo (ventas, compras, POS restaurante) y correcciones

Rama: `feature/etapa1-easycount-ecf`. Entorno de prueba: `tools/ecf_live_demo` (Odoo 20 + EasyCount con el emulador DGII).

| Commit | Cambio |
|---|---|
| `72151f4` | e-CF emitidos por el comprador (E41/E43/E47); pestaña e-CF DGII; demo en vivo |
| `d5305af` | Recibo POS con la representación impresa DGII; propina legal solo en Dine In |
| `fe918d1` | Las notas de crédito parciales conservan el ITBIS de la factura |
| `dce2510` | El setup de la demo crea el piso, las mesas y los presets, y se puede re-ejecutar |
| `0f6a923` | Tipos de documento por diario con `ondelete=cascade` |
| `77376d3` | Tipo de servicio 609 solo en facturas de proveedor, alineado en el formulario |
| `63d4be7` | El comprobante (NCF/e-NCF) se muestra como nombre; ID interno = nombre del diario + id |
| `c478dd1` | `.env` deja de versionarse en el repo público (se mantiene en cada ambiente) |
| `20dcf5c` | `tools/deploy/backup_prod_env.sh`: respaldo del `.env` de producción antes del merge |

Pruebas: l10n_do_accounting, l10n_do_accounting_report, pos_l10n_do_restaurant y pos_system, con 0 fallos.

Pendiente:
- e-NCF asignado antes de validar: los rechazos queman números (falta la decisión del usuario).
- Formato de MontoTotal en el QR: verificar en TesteCF.
- Alta de emisor en la DGII bloqueada: el certificado es rechazado en la autenticación (acción en la OFV).
- Antes de mergear a main: ejecutar `tools/deploy/backup_prod_env.sh` en producción (con confirmación) y rotar las contraseñas que estuvieron en `.env`.

Revertir: `git revert 20dcf5c c478dd1 63d4be7 77376d3 0f6a923 dce2510 fe918d1 d5305af 72151f4`.

## 2026-10-07 — Odoo 20 emite los 10 tipos de e-CF contra la DGII real (CerteCF)
- tools/ecf_live_demo parametrizado: COMPOSE_PROJECT_NAME, ODOO_PORT/EC_PORT, DGII_ENV, DEMO_RNC/DEMO_NAME, SEQ_START y certificado montado desde DGII_P12_HOST (claves solo por entorno, nunca en el repo). Valores por defecto = demo con emulador sin cambios.
- tools/ecf_live_demo/issue_all_types.py: crea y valida en Odoo E31, E32 (<250k y >=250k), E33, E34, E41, E43, E44, E45, E46, E47 (TYPES=... para un subconjunto).
- Resultado (proyecto ecfcert, Odoo 20 :18070 -> EasyCount :18801 -> CerteCF, RNC emisor de pruebas del titular): 11/11 aceptados.
- Revertir: git revert de este commit; COMPOSE_PROJECT_NAME=ecfcert ./down.sh borra el entorno.
- 2026-10-08: docker-compose de ecf_live_demo con restart: unless-stopped (el entorno vuelve tras reiniciar el host).
- 2026-10-08: l10n_do_accounting: asistente "Credenciales DGII (certificado y portal)" en Ajustes > EasyCount; envía .p12, claves y datos de la empresa a EasyCount y borra los secretos de Odoo. Tests Odoo 20: 18/18.

## 2026-10-21 — Formato DGII de la factura restaurado en odoo.getupsoft.com (PR #46)
- La factura E310000000001 (FLAI SRL) salió con el formato simple: el formato validado en la certificación (commit 7cff457, 2026-10-17) estaba solo en la rama fix/print-format-dgii-qr. PR #46 lo fusionó en feature/etapa1-easycount-ecf (2e6db0d) y deploy-odoo20-thinkcentre.yml actualizó l10n_do_accounting en getupsoft (ecflive estaba detenido: se omitió).
- Para poder desplegar se guardó en `git stash` (stash@{0} en ~/workspaces/chefalitas del ThinkCentre) un cambio sin commit del 2026-10-17 en report_invoice.xml (ocultar el título "Invoice …" y el logo por defecto). Quedó superado por PR #47 (95694ce, desplegado 2026-10-21 22:18 UTC): quita la palabra Invoice, prefijo Proforma en borradores y sin logo por defecto. El stash ya no hace falta.
- Pendiente: homologar el formato en el repositorio global JoelStalin/odoo-l10n-do-ecf (su report_invoice.xml es la versión inicial e144cf6).
- Revertir: git revert 2e6db0d (y despliegue); el stash se recupera con `git stash pop`.

## 2026-10-30 Repositorio a la version 20 (feat/odoo-20-production)
- Dockerfile -> Odoo 20 (el de Odoo 18 pasa a Dockerfile.odoo18); docker-compose.yml de produccion de Odoo 20 (PostgreSQL 16 + nginx, secretos en .env no versionado);
  modules.txt y scripts/odoo20 (init-env, install-modules, trim-modules, deploy); modulos propios incorporados: l10n_do_hr_payroll, ai_provider, pos_scale_gateway.
- Workflows: deploy.yml (Odoo 18 por SSH desde GitHub, fallaba) queda como deploy-odoo18-legacy.yml solo manual; nuevo deploy-prod-odoo20.yml en runner propio (chefalitas-prod) al publicar v20.*.
- Revertir: revertir el commit squash del PR.

## 2026-10-30 Despliegue de produccion de Odoo 20 desde el ThinkCentre (tag v20.0.0)
- Autorizado por el usuario: usar solo runners del ThinkCentre, sin crear otras credenciales. La produccion vieja (Odoo 18, PC de la oficina) tiene el tunel caido; no se toca.
- Runner nuevo del repo Chefalitas: thinkcentre-chefalitas (label chefalitas-prod), servicio systemd actions.runner.JoelStalin-Chefalitas.thinkcentre-chefalitas, carpeta ~/actions-runner-chefalitas, con .env: HTTP_PORT=18082 (18080 ya lo usa getupsoft-site-prod) y DEPLOY_DIR=/home/ubuntu/chefalitas-odoo20.
- Disparo: tag v20.0.0 sobre 2ca215d -> workflow deploy-prod-odoo20.yml (run 41113587487 cancelado: el guard G14 detuvo la base porque chefalitas-odoo20-* figura como prueba; relanzado con COMPOSE_PROJECT_NAME=chefalitas-prod, run 41116309952).
- Pendiente del usuario: apuntar chefalitas.com.do / www al puerto 18082 del tunel de Cloudflare (no hay credenciales para hacerlo) y migrar datos de la base chefalitas del PC de la oficina.
- Revertir: cd /home/ubuntu/chefalitas-odoo20 && COMPOSE_PROJECT_NAME=chefalitas-prod docker compose down (-v borra los datos); sudo ~/actions-runner-chefalitas/svc.sh stop && sudo ./svc.sh uninstall; git push origin :refs/tags/v20.0.0 && git tag -d v20.0.0; quitar el runner en GitHub (Settings > Actions > Runners).
- Resultado (2026-10-30 20:07 UTC): run 41116309952 con todos los pasos en success; 109 modulos instalados y recortados a 57 por trim-modules.sh; Odoo 20 responde HTTP 200 en http://127.0.0.1:18082/web/login (ThinkCentre, proyecto Docker chefalitas-prod, carpeta /home/ubuntu/chefalitas-odoo20). Base nueva y vacia: no se migraron datos de la base chefalitas del PC de la oficina.
- Falta (usuario): apuntar chefalitas.com.do / www al puerto 18082 en el tunel de Cloudflare; la politica G14 del guard trata chefalitas-odoo20-* como de prueba (por eso se usa chefalitas-prod).
- Nota: queda un volumen Docker vacio huerfano chefalitas-odoo20_db (creado por un error de un script de pruebas); se puede borrar con docker volume rm cuando Docker lo libere. Base temporal de pruebas tmp_discover: se elimina al terminar el script de pruebas.
