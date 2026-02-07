# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID


def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
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
