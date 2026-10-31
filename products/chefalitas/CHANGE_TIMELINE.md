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

## 2026-10-31 Formato de factura de odoo.getupsoft.com: se restaura el validado y el despliegue recrea contenedores obsoletos
- Dano: la rama fix/remove-proforma-label-dgii (Gemini) quedo activa en ~/workspaces/chefalitas (el directorio que monta odoo.getupsoft.com) y su l10n_do_accounting se aplico a la base getupsoft (2026-10-31 02:37 UTC). Cambiaba la cabecera de dos columnas por una tabla, quitaba los estados Proforma/Cancelled/Credit Note del titulo y agregaba una plantilla que oculta el titulo en web.external_layout_body (todos los reportes).
- Correccion: se redespliega feature/etapa1-easycount-ecf, cuyo report_invoice.xml es identico al validado (51117e3, PR #47), con deploy-odoo20-thinkcentre.yml y -u l10n_do_accounting. La rama de Gemini NO se borra y NO debe desplegarse.
- Causa del primer intento fallido (run 41198020870): el contenedor getupsoft-odoo20-odoo-1 habia perdido su capa de disco (docker exec: rootfs no such file). El workflow ahora detecta eso y lo recrea desde su proyecto compose antes de actualizar (unos 30-40 s de caida).
- Revertir: git revert del commit del PR y volver a ejecutar el workflow.

## 2026-10-31 Facturas sin estilos ni QR en odoo.getupsoft.com: causa y correccion (fix/getupsoft-report-url)
- Sintoma: el usuario descargo B0200000001 (5).pdf (31/10 08:06) con la cabecera apilada, titulo duplicado, tipografia del sistema y, en las e-CF, el QR sin dibujar. La referencia correcta es E310000000001.pdf (21/10, formato de certificacion: dos columnas, QR, codigo de seguridad y fecha de firma digital).
- Causa: web.base.url de la base getupsoft quedo en http://127.0.0.1:18070 desde 2026-10-30 21:37 UTC (sesion del administrador entrando por esa direccion al probar). wkhtmltopdf corre DENTRO del contenedor y pide los estilos y la imagen del QR a esa URL, donde el puerto 18070 no existe (por dentro Odoo escucha en 8069). Las plantillas del 21/10 estaban bien.
- Prueba antes de cambiar nada: con report.url=http://localhost:8069 dentro de una transaccion revertida, E310000000001 y B0200000001 salen identicas a la referencia (QR incluido) y no se guardo ningun parametro.
- Correccion: deploy-odoo20-thinkcentre.yml fija en la base getupsoft report.url=http://localhost:8069, web.base.url=https://odoo.getupsoft.com y web.base.url.freeze=True (idempotente, antes del reinicio que limpia la cache).
- Pendiente de comprobar: Chefalitas Odoo 20 (18082) tiene web.base.url=http://localhost:8069; una prueba desde dentro del contenedor dio timeout y hay que confirmar que sus PDF salen con estilos y QR.
- Revertir: git revert del commit del PR y volver a ejecutar el workflow; los parametros se pueden borrar de Ajustes > Tecnico > Parametros del sistema.

## 2026-10-31 Produccion corregida y guardian del formato de factura (feat/guardian-formato-factura)
- Produccion (odoo.getupsoft.com): run 41200245577 en success; fijo report.url=http://localhost:8069, web.base.url=https://odoo.getupsoft.com y web.base.url.freeze=True en la base getupsoft. Verificado imprimiendo desde produccion E310000000001 y B0200000001 (sin guardar adjuntos): salen identicas a la referencia de certificacion, con QR, codigo de seguridad y fecha de firma.
- Guardian para que nadie vuelva a danar el formato: scripts/guard/check_invoice_format.sh (huella sha256 de report_invoice.xml y report_invoice_preview.xml, exige QR/codigo de seguridad/fecha de firma de la DGII y prohibe heredar web.external_layout_body/report_layout/html_container/minimal_layout desde l10n_do_accounting); hooks de git en .githooks (pre-commit y commit-msg, se activan con bash scripts/guard/install-hooks.sh); workflow guard-invoice-format.yml en cada PR y push; compuerta en deploy-odoo20-thinkcentre.yml (un formato danado no se despliega); CODEOWNERS.
- Cambiar el formato es posible solo con aprobacion del titular: regenerar la huella (--update) y poner [formato-factura-aprobado] en el commit y en el PR.
- Probado: aprueba la version buena y rechaza la danada de Gemini (por huella y por tocar el diseno base).
- Limite: los hooks locales se saltan con --no-verify; el control real es el workflow en el PR. Recomendado (lo hace el titular): activar en GitHub la proteccion de rama exigiendo el check "Guardian del formato de factura" y la revision de CODEOWNERS.
- Revertir: git revert del commit del PR; los parametros de la base se borran en Ajustes > Tecnico > Parametros del sistema.

## 2026-10-31 Regresion mia: el Odoo de getupsoft perdio la red de EasyCount (fix/getupsoft-red-easycount)
- Al recrear getupsoft-odoo20-odoo-1 (PR #58, para arreglar el formato de factura) el contenedor perdio la conexion manual a la red easycount-prod-net: solo conserva getupsoft-odoo20_default y no resuelve easycount-api. Efecto: toda emision e-CF desde odoo.getupsoft.com falla con "EasyCount no pudo asignar el e-NCF: No se pudo conectar con EasyCount (name resolution)". Descubierto al publicar el borrador 6 (E31 de RD$ 1 a Domingo): fallo seguro, no se envio nada a la DGII.
- Correccion: el workflow conecta el contenedor a easycount-prod-net en cada despliegue (idempotente) y falla si el contenedor no resuelve easycount-api, para no dejar la emision rota en silencio.
- Tambien se corrigio la configuracion del ITBIS 18% (impuesto 181 y grupo 63): estaban marcados con pais Estados Unidos (233) y la empresa es dominicana (61); Odoo 20 rechazaba crear facturas con ese impuesto. Ahora ambos son DO.
- Borradores creados (sin publicar): factura 6 = E31 a SUPER COLMADO DOMINGO TORRES EIRL (130610177) y factura 7 = E31 a "Chefalitas y algo mas" (133136122, cliente creado id 22 con el nombre de la base vieja: confirmar la razon social registrada en la DGII), ambas RD$ 1.00 + ITBIS 18% = 1.18, emisor Joel Stalin Martinez Espinal.
- Revertir: git revert del commit del PR y volver a ejecutar el workflow.
