# -*- coding: utf-8 -*-
{
    'name': 'ORCA Odoo MCP Bridge & DTO Gateway',
    'version': '20.0.1.0.0',
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
    'post_init_hook': 'post_init_hook',
    'data': [
        'security/ir.access.csv',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
