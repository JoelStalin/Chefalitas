
{
    'name': 'POS Any Printer Local',
    'version': '18.0.1.0.0',
    'category': 'Point of Sale',
    'summary': 'Permite imprimir recibos en cualquier impresora local desde el TPV de Odoo a través de un agente WebSocket.',
    'author': 'Your Name',
    'website': 'https://www.yourwebsite.com',
    'depends': ['point_of_sale'],
    'secuence': 2,
    'data': [
        'views/pos_config_view.xml',
    ],
    'assets': {
        'point_of_sale.assets': [
            'pos_any_printer_local/static/src/js/main.js',
            'pos_any_printer_local/static/src/js/local_printer_service.js',
            'pos_any_printer_local/static/src/js/Screens/ReceiptScreen/ReceiptScreen.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
