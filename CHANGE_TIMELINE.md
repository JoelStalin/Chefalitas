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
