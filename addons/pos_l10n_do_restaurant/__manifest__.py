{
    "name": "POS Restaurante RD: ITBIS y propina legal",
    "summary": "Presets del POS (comer aqui / para llevar / delivery) con las posiciones fiscales DGII",
    "description": """
Conecta los presets de pos_restaurant con las posiciones fiscales del plan contable
dominicano de Odoo (l10n_do):

* Comer aqui -> "Restaurantes": ITBIS 18% + propina legal 10% (Ley 16-92 art. 228).
  La propina no forma parte de la base del ITBIS.
* Para llevar / Delivery -> "Para Llevar": solo ITBIS 18%, sin propina legal.

En el e-CF la propina se informa como impuesto adicional DGII codigo 001 (EasyCount).
""",
    "version": "20.0.1.0.0",
    "category": "Sales/Point of Sale",
    "author": "GetUpSoft",
    "license": "LGPL-3",
    "depends": ["pos_restaurant", "l10n_do"],
    "data": [],
    "post_init_hook": "post_init_hook",
    "installable": True,
}
