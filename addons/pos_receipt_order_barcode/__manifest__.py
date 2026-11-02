{
    "name": "POS: código de barras del pedido en el recibo",
    "summary": "Imprime en el recibo un código de barras con la referencia del pedido; al escanearlo en la pantalla "
               "de pedidos se abre el pedido para hacer la devolución.",
    "version": "20.0.1.0.0",
    "author": "GetUpSoft",
    "license": "LGPL-3",
    "category": "Point of Sale",
    "depends": ["point_of_sale"],
    "data": ["views/pos_order_receipt_templates.xml"],
    "assets": {
        "point_of_sale._assets_pos": [
            "pos_receipt_order_barcode/static/src/app/screens/ticket_screen/ticket_screen.js",
        ],
    },
    "installable": True,
    "application": False,
}
