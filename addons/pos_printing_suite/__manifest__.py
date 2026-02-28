# -*- coding: utf-8 -*-
{
    "name": "POS Printing Suite",
    "version": "18.0.1.0.0",
    "license": "LGPL-3",
    "category": "Sales/Point of Sale",
    "summary": "Unified POS printing: Local Agent (Windows), HW Proxy, Self-Order",
    "author": "GetUpSoft",
    "depends": ["point_of_sale", 'pos_self_order'],
    "post_init_hook": "post_init_hook",
    "assets": {
        # Legacy compatibility: /pos/web (older POS route) may rely on this bundle key.
        "point_of_sale.assets": [
            "pos_printing_suite/static/src/entrypoints/pos_printing_suite_pos_entry.js",
        ],
        "point_of_sale._assets_pos": [
            "pos_printing_suite/static/src/entrypoints/pos_printing_suite_pos_entry.js",
        ],
        "pos_self_order.assets": [
            "pos_printing_suite/static/src/entrypoints/pos_printing_suite_self_order_entry.js",
        ],
    },
    "data": [
        "security/ir.model.access.csv",
        "security/security.xml",
        "views/pos_config_views.xml",
        "views/agent_install_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
}
