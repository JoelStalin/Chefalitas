# -*- coding: utf-8 -*-
{
    'name': 'ORCA Bridge',
    'version': '20.0.2.0.0',
    'category': 'Technical/API',
    'summary': 'Odoo consumes the ORCA service: OAuth 2.0 connector, ORCA admin user/API key, change events',
    'description': """
The ORCA bridge (DTOs with ORCA ids, exposure policy, audit log, MCP server) is a function of the ORCA
service. This addon is the Odoo side:

* Settings > ORCA: OAuth 2.0 connector (authorization code + PKCE). The company and the connector are
  registered in ORCA settings; an ORCA administrator approves the connection on ORCA's consent screen.
* On approval Odoo hands ORCA the JSON-2 API key of the dedicated "ORCA" administrator user: ORCA controls
  the whole Odoo 20 environment and the permissions are managed in ORCA.
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
