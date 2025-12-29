{
    "name": "POS Any Printer Local",
    "version": "18.0.1.1.0",
    "category": "Point of Sale",
    "summary": "Imprime recibos y comandas en impresoras de Windows mediante un agente local (HTTP/HTTPS).",
    "author": "Your Name",
    "website": "https://www.yourwebsite.com",
    "depends": ["point_of_sale"],
    "sequence": 3,
    "data": [
        "security/ir.model.access.csv",
        "views/pos_config_view.xml"
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "pos_any_printer_local/static/src/js/local_printer_service.js",
            "pos_any_printer_local/static/src/app/local_agent_printer.js",
            "pos_any_printer_local/static/src/overrides/models/pos_store.js",
            "pos_any_printer_local/static/src/js/Screens/ReceiptScreen/ReceiptScreen.js"
        ]
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3"
}
