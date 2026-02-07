# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID


def post_init_hook(env_or_cr, registry=None):
    # Odoo 18 calls post_init_hook(env). Older versions call (cr, registry).
    if registry is None:
        env = env_or_cr
    else:
        env = api.Environment(env_or_cr, SUPERUSER_ID, {})
    # Try to place menu under POS Configuration if it exists.
    candidates = [
        "point_of_sale.menu_point_of_sale_configuration",
        "point_of_sale.menu_pos_configuration",
        "point_of_sale.menu_point_of_sale_config",
        "point_of_sale.menu_point_of_sale_root",
        "point_of_sale.menu_point_of_sale",
    ]
    parent = None
    for xmlid in candidates:
        try:
            parent = env.ref(xmlid)
            break
        except ValueError:
            continue
    if not parent:
        return
    try:
        menu = env.ref("pos_printing_suite.menu_pos_print_device")
    except ValueError:
        return
    menu.write({"parent_id": parent.id})
