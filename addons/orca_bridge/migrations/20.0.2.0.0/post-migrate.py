def migrate(cr, version):
    """20.0.2: ORCA reaches Odoo with the ORCA user's JSON-2 API key; the old shared token is gone
    (including the value that leaked in the public repository)."""
    cr.execute("DELETE FROM ir_config_parameter WHERE key = 'orca.api_token'")
