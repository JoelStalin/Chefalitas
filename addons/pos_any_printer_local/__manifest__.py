{
    'name': 'POS Local Printer (search by name)',
    'version': '1.0.0',
    'category': 'Point of Sale',
    'summary': 'Impresión local: busca impresora por nombre en la máquina cliente y envía trabajos al agente local',
    'description': 'Usa un agente local (127.0.0.1:9100) para listar impresoras del cliente y enviar trabajos por nombre.',
    'depends': ['point_of_sale'],
    'data': [
        'views/pos_assets.xml',
        'views/pos_config_view.xml',
        'security/ir.model.access.csv',
    ],
    'qweb': [],
    'installable': True,
    'application': False,
}
