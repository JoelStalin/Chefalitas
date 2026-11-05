{
    "name": "Fripick Orders",
    "summary": "Captures closed POS orders per company, prints kitchen tickets and Fripick labels, syncs companies daily "
               "and issues the monthly invoice with its fiscal voucher on the 1st.",
    "version": "20.0.1.0.0",
    "author": "GetUpSoft",
    "license": "LGPL-3",
    "category": "Point of Sale",
    "depends": ["point_of_sale", "account", "pos_printing_suite"],
    "data": [
        "security/ir.access.csv",
        "data/ir_cron.xml",
        "report/label_a4.xml",
        "views/fripick_views.xml",
        "views/res_company_views.xml",
    ],
    "installable": True,
    "application": False,
}
