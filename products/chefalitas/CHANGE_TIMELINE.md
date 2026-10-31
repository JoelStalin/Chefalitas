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

## 2026-10-30 Asistente "Buscar impresoras en la red" de pos_printing_suite (feat/pos-printing-discover, PR Chefalitas#52)
- Menu Punto de venta > Configuracion > Buscar impresoras en la red: escanea el puerto 9100 de una red privada (maximo 1024 equipos; rechaza redes publicas) y agrega las elegidas al punto de venta como impresora de caja o cocina, sin duplicar las ya registradas.
- Pruebas ejecutadas en una base temporal (tmp_discover, ya eliminada) con la imagen de produccion y la rama montada: 0 fallos, 0 errores (12 tests de pos_printing_suite, incluidos los 3 nuevos de test_discover_printers.py).
- No se toco la base de produccion. Pendiente: fusionar el PR a feat/odoo-20-production y redesplegar; unificar las conexiones directa/gateway de fripick_orders (requiere migrar datos de Fripick).
- Revertir: revertir el commit del PR y volver a ejecutar el workflow deploy-prod-odoo20.

## 2026-10-30 Merges a main autorizados y redespliegue v20.0.1
- Autorizado por el usuario: cualquier merge a main. Fusionados: Chefalitas#51 (timeline), #52 (a feat/odoo-20-production) y #53 (asistente "Buscar impresoras en la red", cherry-pick de #52 sobre main porque main ya tenia el trabajo de Odoo 20 por #50); odoo-l10n-do-ecf#2 (nomina Odoo 20) y #3 (modulo l10n_do_recipe_margin).
- Redespliegue de produccion en el ThinkCentre: tag v20.0.1 sobre main (7f8b838), workflow deploy-prod-odoo20 (run 41133982657), proyecto Docker chefalitas-prod, puerto 18082.
- El servidor de la oficina sigue caido; el usuario pidio probar con el contenedor local. El modulo de codigo de barras llega en un repo nuevo de Gemini (pendiente de integrar).
- Revertir: git revert del commit del PR en main y publicar un tag v20.0.2 (el workflow redespliega); para quitar el contenedor: COMPOSE_PROJECT_NAME=chefalitas-prod docker compose down en /home/ubuntu/chefalitas-odoo20.

## 2026-10-30 Resultado del redespliegue v20.0.1 (run 41133982657)
- Verificado en la base real chefalitas del ThinkCentre (proyecto chefalitas-prod, puerto 18082) a las 22:04 UTC: el menu "Buscar impresoras en la red" existe y esta activo (ir_ui_menu id 336), los modelos pos.printing.discover.wizard y pos.printing.discover.line estan registrados y pos_printing_suite figura installed 20.0.1.0.0. Login HTTP 200 durante y despues de la actualizacion.
- Pruebas automaticas previas en base temporal: 0 fallos, 0 errores.
- Revertir: git revert del commit del PR #53 en main y publicar el tag v20.0.2 (el workflow redespliega y -u quita las vistas).

## 2026-10-30 trim-modules.sh reintenta cuando Odoo ejecuta una accion programada (fix/trim-modules-cron-retry)
- Causa: en el redespliegue v20.0.1 (run 41133982657) la actualizacion de modulos termino bien, pero trim-modules.sh fallo al desinstalar el extra "rpc": el Odoo que seguia sirviendo ejecutaba un cron y Odoo bloquea las operaciones de modulos en ese momento ("Odoo is currently processing a scheduled action"). En el primer despliegue no ocurrio porque aun no habia un Odoo corriendo.
- Arreglo: ante ese error se hace rollback, se espera 20 s y se reintenta (hasta 15 veces).
- Revertir: revertir el commit del PR y publicar un tag nuevo (v20.0.3) para redesplegar.

## 2026-10-30 Estado final: Odoo 20 de Chefalitas en el ThinkCentre (tag v20.0.2)
- Run 41136187011 (tag v20.0.2) terminado en success: construccion de imagen, actualizacion de modulos (-u) y recorte (trim-modules.sh) completos. El run anterior (v20.0.1, 41133982657) habia fallado solo en el recorte, por un cron de Odoo en curso; lo corrige el PR #56.
- Verificado a las 22:17 UTC en la base real chefalitas (proyecto chefalitas-prod, puerto 18082): login HTTP 200, menu "Buscar impresoras en la red" activo (ir_ui_menu 336), modelos pos.printing.discover.wizard y .line registrados, 57 modulos instalados, contenedores nginx, odoo y db arriba.
- Pendiente del usuario: apuntar chefalitas.com.do y www al puerto 18082 en el tunel de Cloudflare, actualizar la politica G14 del guard (trata chefalitas-odoo20-* como de prueba), y migrar datos de la base del PC de la oficina. Modulo de codigo de barras: llega en un repo nuevo de Gemini.
- Revertir: git revert del commit en main y publicar un tag nuevo (v20.0.3) para redesplegar; para bajar el servicio: COMPOSE_PROJECT_NAME=chefalitas-prod docker compose down en /home/ubuntu/chefalitas-odoo20.

## 2026-10-31 Formato de factura de odoo.getupsoft.com restaurado (run 41198272215)
- Dano: la rama fix/remove-proforma-label-dgii (Gemini) quedo activa en ~/workspaces/chefalitas, el directorio que monta odoo.getupsoft.com, y su l10n_do_accounting se aplico a la base getupsoft (2026-10-31 02:37 UTC). Cambiaba la cabecera de dos columnas por una tabla, quitaba los estados Proforma/Cancelled/Credit Note del titulo y agregaba una plantilla que oculta el titulo en web.external_layout_body, que afecta a todos los reportes.
- Correccion: se redespliego feature/etapa1-easycount-ecf (report_invoice.xml identico al validado en 51117e3, PR #47) con deploy-odoo20-thinkcentre.yml y -u l10n_do_accounting. El primer intento (run 41198020870) fallo porque el contenedor getupsoft-odoo20-odoo-1 habia perdido su capa de disco (docker exec: rootfs no such file); el PR #58 hace que el workflow lo recree desde su proyecto compose antes de actualizar (unos 30-40 s de caida).
- Verificado en la base getupsoft el 2026-10-31 11:48 UTC: vista external_layout_body_clean_title = 0, cabecera sin table-borderless, titulo con Proforma/Cancelled/Credit Note, login 200 en 18070 y en odoo.getupsoft.com.
- La rama de Gemini NO se borro y NO debe desplegarse. Pendiente: que Gemini no cambie de rama ni edite a mano el directorio ~/workspaces/chefalitas (es el codigo en vivo); homologar el formato en el repo global.
- Revertir el arreglo del workflow: git revert del commit del PR #58 en feature/etapa1-easycount-ecf y volver a ejecutar el workflow.

## 2026-10-31 Revision de todos los formatos de factura (huella md5 contra la version validada 51117e3)
- Version validada: report_invoice.xml d00eb626, report_invoice_preview.xml 2fb3376f.
- Correctos: Chefalitas main y rama de despliegue (Odoo 20 del puerto 18082 y odoo.getupsoft.com), odoo-l10n-do-ecf (preview).
- Distintos y corregidos: report_invoice.xml de odoo-l10n-do-ecf (PR #4, fusionado a main) y de odoo-orca-global-addons (PR #1, abierto: es la rama activa de Gemini, ningun sitio en vivo la usa). Antes tenian la version inicial (209 lineas, 008a2804). El modulo global ya tiene los campos que usa el formato validado.
- No se tocaron otras diferencias del modulo global (res_partner.py, account_journal.py, res_partner_views.xml): no son de formato.
- Revertir: git revert del commit del PR #4 en odoo-l10n-do-ecf.

## 2026-10-31 Modulo orca_stock_logistics_barcode: no instala en Odoo 20 (causa confirmada)
- Pruebas en base temporal (tmp_barcode, ya eliminada): la instalacion falla con `TypeError: Model 'product.packaging' does not exist in registry`.
- Causa: en Odoo 20 el modelo product.packaging YA NO EXISTE. El empaque por producto con codigo de barras es ahora `product.uom` (campos barcode, product_id, uom_id; product.product.product_uom_ids; uom.uom.product_uom_ids). Solo quedan stock.package* para empaques fisicos de bodega. Verificado dentro de la imagen chefalitas-odoo:20.0.
- El modulo (hecho para el diseno de Odoo 17-19) hereda product.packaging en models/product_packaging_barcode.py (311 lineas) y lo usa en stock_picking_barcode.py y barcode_enrichment_service.py: no se arregla con una dependencia, requiere portarlo a product.uom (el multiplicador sale de la relacion de uom.uom, ya no de un campo qty).
- Estado: NO esta en main ni desplegado. La rama feat/orca-stock-logistics-barcode (4219b83) queda como borrador sin fusionar.
- Siguiente paso: portar a product.uom y volver a correr las pruebas en una base temporal.

## 2026-10-31 Guardian del formato de factura tambien en main
- Mismo guardian que en la rama de despliegue (scripts/guard, .githooks, workflow guard-invoice-format.yml, CODEOWNERS) y compuerta en deploy-prod-odoo20.yml: un formato de factura distinto del validado en la certificacion DGII no se fusiona ni se despliega.
- Activar los hooks locales en cada clon: bash scripts/guard/install-hooks.sh. Cambios de formato: solo con aprobacion del titular ([formato-factura-aprobado] y bash scripts/guard/check_invoice_format.sh --update).
- Revertir: git revert del commit del PR.
