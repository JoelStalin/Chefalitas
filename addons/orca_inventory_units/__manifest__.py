{
    "name": "ORCA Cajas y Libras (inventario y punto de venta)",
    "version": "20.0.1.0.0",
    "summary": "Compra por caja y venta por unidad, relacionadas; productos que se venden por libra con precio por libra y cantidad en libras en el POS",
    "description": """
Cajas y libras para colmados
============================
* Caja y unidad relacionadas: en el producto se indican "Unidades por caja" y el código de barras de la caja.
  Se crea la unidad "Caja xN" (se puede comprar y recibir por caja), el código de la caja en el punto de venta
  (al escanearla suma N unidades) y el empaque que usa el escáner de inventario. El producto se vende por unidad.
* Se vende por libra: marca el producto con la unidad Libra, "para pesar" y disponible en el POS. El precio de venta es
  el precio por libra. Al elegirlo en el POS (sin balanza conectada) pregunta cuántas libras; con balanza se usa el botón de peso.
""",
    "author": "GetUpSoft",
    "website": "https://getupsoft.com.do",
    "license": "LGPL-3",
    "category": "Inventory/Inventory",
    "depends": ["product", "stock", "point_of_sale"],
    "data": [
        "views/product_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "orca_inventory_units/static/src/pos_weigh_prompt.js",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
