# -*- coding: utf-8 -*-
{
    'name': 'ORCA Bridge',
    'version': '20.0.2.0.0',
    'category': 'Technical/API',
    'summary': 'Odoo consumes the ORCA service: ORCA connection settings, dedicated ORCA API user/key, change events',
    'description': """
The ORCA bridge (DTOs with ORCA ids, exposure policy, audit log, MCP server) is a function of the ORCA
service. This addon is the Odoo side:

* Settings > ORCA: ORCA URL, token and connection id; test the connection.
* A dedicated "ORCA" user whose JSON-2 API key ORCA uses to read and modify records
  (its access rights limit what ORCA can do).
* Change notifications (model, event, record ids, field names; no values) pushed to ORCA after commit.
""",
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
        'data/orca_bridge_data.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
