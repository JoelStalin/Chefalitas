# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID


def post_init_hook(env_or_cr, registry=None):
    """Cleanup legacy Printing Devices records after install/upgrade.

    This avoids XML <delete> parsing issues across versions.
    """
    if registry is None:
        env = env_or_cr
    else:
        env = api.Environment(env_or_cr, SUPERUSER_ID, {})

    xmlids = [
        "pos_printing_suite.menu_pos_print_device",
        "pos_printing_suite.action_pos_print_device",
        "pos_printing_suite.view_pos_print_device_tree",
        "pos_printing_suite.view_pos_print_device_form",
        "pos_printing_suite.view_pos_printer_form_printing_suite",
    ]
    for xmlid in xmlids:
        record = env.ref(xmlid, raise_if_not_found=False)
        if record:
            try:
                record.unlink()
            except Exception:
                # Ignore failures to avoid blocking module install/upgrade.
                pass

    try:
        env["pos.config"]._normalize_existing_hw_proxy_ports()
    except Exception:
        # Avoid blocking install if normalization fails.
        pass
