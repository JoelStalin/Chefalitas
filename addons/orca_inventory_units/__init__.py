from . import models


def post_init_hook(env):
    """Odoo 20 ships the imperial pound deactivated and hanging from the ounce: activate it and anchor it to the gram."""
    pound = env.ref("uom.product_uom_lb", raise_if_not_found=False)
    gram = env.ref("uom.product_uom_gram", raise_if_not_found=False)
    if pound and gram:
        pound.write({"active": True, "relative_uom_id": gram.id, "relative_factor": 453.59237})
