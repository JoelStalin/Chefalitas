{
    "name": "POS Self Order Any Printer Local",
    "version": "18.0.1.0.0",
    "category": "Point of Sale",
    "summary": "Impresión de Self-Order hacia impresoras de Windows mediante agente local.",
    "author": "Your Name",
    "website": "https://www.yourwebsite.com",
    "depends": ["pos_self_order", "pos_any_printer_local"],
    "assets": {
        "pos_self_order.assets": [
            "pos_self_order_any_printer_local/static/src/overrides/models/self_order_service.js"
        ]
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3"
}
