{
    'name': 'Ponint of Sale client printer',
    'version': '1.0.0',
    'author': 'Joel S. Martinez',
    'category': 'Point of Sale',
    'summary': 'Unifica pos_any_printer, pos_self_order y otros módulos POS',
    'description': 'Módulo único que permite impresión en cualquier impresora Windows y autoservicio.',
    'depends': ['point_of_sale', 'stock', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/pos_client_printer_views.xml',
        'views/pos_client_config_views.xml',
        'data/pos_client_printer_data.xml',
    ],
    'assets': {
        'point_of_sale.assets': [
            'pos_client_printer/static/src/js/pos_client_printer.js',
        ],
    },
    'installable': True,
    'application': False,
}
