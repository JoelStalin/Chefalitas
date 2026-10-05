# -*- coding: utf-8 -*-
{
    'name': 'ORCA Odoo MCP Bridge & DTO Gateway',
    'version': '18.0.1.0.0',
    'category': 'Technical/API',
    'summary': 'Exposes standardized DTOs and control endpoints for ORCA MCP Agent (Account, DGII e-NCF, POS, Stock, Kitchen)',
    'author': 'GetUpSoft / ORCA Team',
    'website': 'https://getupsoft.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'account',
        'stock',
        'point_of_sale',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/orca_default_config.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
