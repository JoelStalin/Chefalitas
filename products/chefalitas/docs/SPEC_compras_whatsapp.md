# Compras por WhatsApp, recetas e inventario con ORCA (Chefalitas, Odoo 20)

Estado: borrador para implementar por etapas. Fecha: 2026-10-08.

## Objetivo

Los empleados envían por WhatsApp la foto de cada factura de compra. ORCA la lee, confirma la transcripción con
el empleado, crea en Odoo 20 la orden de compra y la factura de proveedor con la imagen adjunta, recibe la
mercancía en inventario, descuenta los insumos de cada plato vendido según su receta, y sugiere precios de venta
según el costo real de la materia prima.

## Decisiones del usuario (2026-10-08)

- Canal: los dos. Número oficial de WhatsApp Business (Cloud API de Meta, chats 1:1, sin riesgo de bloqueo) y,
  además, un grupo leído con una librería no oficial, aceptando el riesgo de bloqueo del número.
- Base: el módulo Enterprise `whatsapp` de `orca_addons`, migrado a Odoo 20 (fuera de Git: licencia Enterprise).
- Lectura de facturas: ORCA orquesta con modelos locales por defecto; proveedores en la nube (Claude, ChatGPT…)
  opcionales, configurados con token.
- Recetas: ORCA las estima y las valida con sus propias pruebas.

## Flujo

1. Un empleado autorizado envía la foto (chat oficial o grupo). Mensajes de números no autorizados se ignoran.
2. Odoo crea un `purchase.intake` (estado `received`) con la imagen y lo pasa a ORCA.
3. ORCA extrae los datos (ver "Lectura") y devuelve un DTO con confianza por campo.
4. Odoo responde por WhatsApp con el resumen: proveedor, RNC, NCF, fecha, líneas, ITBIS y total.
   El empleado responde `SI` para confirmar, o corrige en texto (`linea 2 cantidad 5`, `proveedor ...`).
5. Al confirmar: orden de compra (proveedor por RNC; si no existe, se crea), confirmada; recepción validada
   (entra al inventario); factura de proveedor con NCF y la imagen adjunta. La factura queda en borrador para
   revisión contable (no se publica sola).
6. Cada línea se asocia a un producto insumo. La primera vez ORCA propone el producto y el empleado lo confirma;
   la asociación se guarda (`product.supplierinfo` con el nombre del proveedor) y la siguiente vez es automática.

## Lectura (ORCA, NestJS)

Pipeline por capas, de lo más barato y determinista a lo más caro:

1. OCR local (Tesseract, español) → texto.
2. Modelo local pequeño (Ollama) → JSON con el esquema de factura.
3. Validaciones deterministas → confianza: suma de líneas = subtotal, ITBIS 18 % (o exento), total = subtotal +
   ITBIS, formato RNC (9 u 11 dígitos), formato NCF (B01/B02/E31…), fecha válida.
4. Si la confianza es baja y hay un proveedor en la nube configurado: se envía la imagen a ese proveedor.
5. Siempre: confirmación del empleado antes de tocar contabilidad o inventario.

Proveedores configurables por empresa en ORCA (token cifrado): `local` (por defecto), `anthropic`, `openai`,
`google`. Se registra qué capa produjo cada lectura y su costo.

## Recetas y porciones

- Cada plato del POS es un producto con lista de materiales tipo **kit** (`mrp.bom`, `phantom`): al vender el plato,
  Odoo descuenta los insumos del inventario automáticamente.
- ORCA propone la receta inicial (insumos y cantidades por porción) a partir del nombre del plato, sus variantes
  (salsas) y los insumos comprados.
- Pruebas propias de ORCA, repetibles:
  - Balance teórico vs. real por periodo: compras − consumo teórico (ventas × receta) − stock contado = merma.
    Una merma fuera de rango señala recetas mal estimadas.
  - Coherencia: ninguna receta con cantidades negativas o cero, unidades compatibles, costo por porción dentro
    de un rango plausible para el precio de venta.
  - Ajuste: ORCA propone correcciones de cantidades cuando la merma de un insumo es sistemática; un gerente las
    aprueba.

## Márgenes y precios

- Costo del plato = suma(cantidad del insumo × costo promedio del insumo), con el costo actualizado por cada
  factura confirmada.
- Margen = (precio − costo) / precio. Objetivo configurable (por categoría).
- Sugerencia: cuando el margen cae bajo el objetivo, ORCA propone el nuevo precio (redondeado a la escala de
  precios del menú) y lo envía al gerente; nunca cambia precios solo.

## Fuera de alcance de la primera entrega

- Pantalla de WhatsApp dentro de Odoo (Discuss): sus plantillas web de Odoo 18/19 no existen en 20; los empleados
  usan WhatsApp en su teléfono, así que no bloquea.
- Facturación electrónica de compras (E41/E43): espera la aprobación de la DGII para Chefalitas.

## Etapas

1. Módulo Odoo `chefalitas_purchase_intake`: modelo, enlace con WhatsApp entrante, confirmación por chat,
   creación de orden de compra, recepción y factura con la imagen. Pruebas con un extractor simulado.
2. Servicio ORCA de lectura: OCR + modelo local + validaciones + proveedores en la nube opcionales.
3. Recetas (kits) propuestas por ORCA, descuento automático por venta, pruebas de merma.
4. Márgenes y sugerencias de precio.
5. Lectura del grupo de WhatsApp (librería no oficial) entrando por el mismo endpoint.
