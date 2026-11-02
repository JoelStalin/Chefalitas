# -*- coding: utf-8 -*-
{
    'name': 'Cambios para Punto de Venta',
    'version': '20.0.1.0.0',
    'license': 'LGPL-3',
    'category': 'Punto de Venta',
    "sequence": 2,
    'summary': 'Cambios para Punto de Venta',
    'complexity': "easy",
    'author': 'Emy Saul Soto',
    'depends': [
        'l10n_latam_invoice_document',
        'sale_management', 'point_of_sale', 'product', 'pos_loyalty'
    ],
    'data': [
        'receipt/pos_order_receipt.xml',
       'views/pos_order/pos_order_views.xml',
    ],
    "assets": {
        'point_of_sale._assets_pos': [
            'pos_system/static/src/**/*',
        ],
    },
    
    
    'installable': True,
    'auto_install': False,
    'application': True,
}
