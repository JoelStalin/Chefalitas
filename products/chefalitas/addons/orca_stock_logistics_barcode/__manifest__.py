{
    "name": "ORCA Advanced Stock Logistics Barcode (OCA v20)",
    "version": "20.0.1.0.0",
    "category": "Inventory/Inventory",
    "summary": "High-performance barcode scanning for pickings & inventory with multi-packaging multiplier, IndexedDB cache, and Open Food Facts enrichment",
    "author": "GetUpSoft",
    "website": "https://getupsoft.com",
    "license": "LGPL-3",
    "depends": [
        "base",
        "stock",
        "barcodes",
        "product",
        "uom",
        "web",
    ],
    "data": [
        "security/ir.access.csv",
        "views/stock_barcode_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "orca_stock_logistics_barcode/static/src/services/barcode_indexeddb_cache.js",
            "orca_stock_logistics_barcode/static/src/components/barcode_scanner_app/barcode_scanner_app.js",
            "orca_stock_logistics_barcode/static/src/components/barcode_scanner_app/barcode_scanner_app.xml",
            "orca_stock_logistics_barcode/static/src/components/barcode_scanner_app/barcode_scanner_app.scss",
        ],
    },
    "installable": True,
    "application": True,
    "auto_install": False,
}
