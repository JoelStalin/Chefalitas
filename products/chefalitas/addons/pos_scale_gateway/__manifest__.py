{
    "name": "POS Scale Gateway",
    "version": "20.0.1.0.0",
    "summary": "Secure outbound scale bridge for remote Odoo POS",
    "category": "Point of Sale",
    "author": "GetUpSoft",
    "license": "LGPL-3",
    "depends": ["point_of_sale"],
    "data": [
        "security/ir.access.csv",
        "views/scale_device_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "pos_scale_gateway/static/src/scale_button.js",
            "pos_scale_gateway/static/src/scale_button.xml",
        ],
    },
    "installable": True,
    "application": False,
}
