# -*- coding: utf-8 -*-
{
    "name": "POS Printing Suite",
    "version": "18.0.1.0.0",
    "license": "LGPL-3",
    "category": "Sales/Point of Sale",
    "summary": "Unified POS printing: Local Agent (Windows), HW Proxy, Self-Order",
    "author": "GetUpSoft",
    "depends": ["point_of_sale"],
    "post_init_hook": "post_init_hook",
    "assets": {
        "point_of_sale._assets_pos": [
            "pos_printing_suite/static/src/**/*.js",
        ],
        "pos_self_order.assets": [
            "pos_printing_suite/static/src/app/printers/*.js",
            "pos_printing_suite/static/src/overrides/self_order_service_patch.js",
        ],
    },
    "data": [
        "security/ir.model.access.csv",
        "security/security.xml",
        "views/pos_config_views.xml",
    ],
    "installable": True,
    "application": False,
}
