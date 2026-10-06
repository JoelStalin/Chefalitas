from odoo import SUPERUSER_ID, api

from odoo.addons.orca_bridge.hooks import ensure_api_token


def migrate(cr, version):
    """Rotate orca.api_token if it still holds the token leaked in the public repository."""
    ensure_api_token(api.Environment(cr, SUPERUSER_ID, {}))
