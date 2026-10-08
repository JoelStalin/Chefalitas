{
    "name": "Chefalitas: compras por WhatsApp con ORCA",
    "version": "20.0.1.0.0",
    "category": "Inventory/Purchase",
    "summary": "Employees send supplier invoice photos over WhatsApp; ORCA reads them, the employee confirms, "
               "Odoo creates the purchase order, the receipt and the vendor bill with the photo attached",
    "author": "GetUpSoft",
    "license": "LGPL-3",
    "depends": ["purchase_stock", "whatsapp", "orca_bridge", "l10n_do_accounting"],
    "data": [
        "security/ir.access.csv",
        "data/ir_sequence.xml",
        "views/purchase_intake_views.xml",
    ],
    "installable": True,
}
