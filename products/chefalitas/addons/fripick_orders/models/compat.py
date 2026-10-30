"""System parameters across Odoo versions: 20 has typed getters (get_str, get_int); 18 and 19 have get_param."""


def param_str(env, key, default=""):
    params = env["ir.config_parameter"].sudo()
    if hasattr(params, "get_str"):
        return params.get_str(key, default)
    return params.get_param(key) or default


def param_int(env, key, default=0):
    params = env["ir.config_parameter"].sudo()
    if hasattr(params, "get_int"):
        return params.get_int(key, default)
    try:
        return int(params.get_param(key) or default)
    except ValueError:
        return default
