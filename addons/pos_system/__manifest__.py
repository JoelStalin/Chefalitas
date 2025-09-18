# -*- coding: utf-8 -*-
{
    'name': 'Cambios para Punto de Venta',
    'version': '1.0.0',
    'license': 'LGPL-3',
    'category': 'Punto de Venta',
    "sequence": 2,
    'summary': 'Cambios para Punto de Venta',
    'complexity': "easy",
    'author': 'Emy Saul Soto',
    'depends': [
        'sale_management', 'point_of_sale', 'product', 'rdbazar_base_addons', 'pos_loyalty'
    ],
    'data': [
       'views/pos_order/pos_order_views.xml',
    ],
    "assets": {
        'point_of_sale._assets_pos': [
            'pos_system/static/src/**/*',
        ],
        'point_of_sale.customer_display_assets': [
            "pos_system/static/src/overrides/components/order_widget/*",
        ],
    },
    
    
    'installable': True,
    'auto_install': False,
    'application': True,
}
