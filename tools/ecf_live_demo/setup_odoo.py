"""Data for the live e-CF demo (run inside `odoo shell -d ecflive`).

Company Chefalitas (test RNC 131793916), DO chart, e-CF issuer through EasyCount (DGII_ENV=LOCAL emulator),
partners for every DGII taxpayer type, restaurant products with ITBIS 18% and an exempt service, and the
POS restaurant. Test data only: no real customers.
"""
import os

env = env  # noqa: F821 - provided by odoo shell
TOKEN = os.environ["EASYCOUNT_TOKEN"]
DO = env.ref("base.do")
company = env.company

company.write({
    "name": "Chefalitas (PRUEBAS e-CF)",
    "vat": "131793916",
    "street": "Av. Winston Churchill 1099",
    "city": "Santo Domingo",
    "country_id": DO.id,
})
if company.chart_template != "do":
    # the module install loaded the generic chart (no country yet): switch to the Dominican one (no entries exist)
    env["account.chart.template"].try_loading("do", company=company, install_demo=False)
    print("chart:", company.chart_template)

company.write({
    "l10n_do_ecf_issuer": True,
    "l10n_do_easycount_enabled": True,
    "l10n_do_easycount_url": "http://easycount:8000",
    "l10n_do_easycount_auth_mode": "token",
    "l10n_do_easycount_token": TOKEN,
})
env["account.journal"].search([("type", "in", ("sale", "purchase")), ("company_id", "=", company.id),
                             ("l10n_latam_use_documents", "=", False)]).write(
    {"l10n_latam_use_documents": True})

# USD rate for the export invoice (1 USD = 59.00 DOP)
env["res.currency"].search([("name", "=", "USD")]).active = True
if not env["res.currency.rate"].search_count([("currency_id", "=", env.ref("base.USD").id), ("company_id", "=", company.id)]):
    env["res.currency.rate"].create({"currency_id": env.ref("base.USD").id, "rate": 1 / 59.0, "company_id": company.id})


def partner(name, vat, payer, country=DO, **kw):
    p = env["res.partner"].search([("name", "=", name)], limit=1)
    vals = {"name": name, "vat": vat, "l10n_do_dgii_tax_payer_type": payer, "country_id": country.id,
            "is_company": payer != "non_payer", **kw}
    return p.write(vals) and p if p else env["res.partner"].create(vals)


partner("ITERATIVO SRL", "131566332", "taxpayer")                       # E31 credito fiscal
partner("JOSE LUIS LOPEZ", "22400559690", "non_payer")                   # E32 consumo / E41 proveedor informal
partner("ZONA FRANCA INDUSTRIAL DE LAS AMERICAS", "101168481", "special")  # E44 regimen especial
partner("MINISTERIO DE INDUSTRIA Y COMERCIO", "401007355", "governmental")  # E45 gubernamental
partner("BLUE OCEAN IMPORTS LLC", "847898798", "foreigner", env.ref("base.us"))  # E46 exportacion
partner("CLOUD SOFTWARE INC", "952315874", "foreigner", env.ref("base.us"))      # E47 pago al exterior
partner("FERRETERIA EL CHINO (gasto menor)", False, "non_payer")                  # E43 gasto menor: sin RNC (XSD)
partner("CONSUMIDOR FINAL", False, "non_payer")                                  # POS sin identificacion

sale_tax = company.account_sale_tax_id
purchase_tax = company.account_purchase_tax_id
exempt_sale = env["account.tax"].search([("company_id", "=", company.id), ("type_tax_use", "=", "sale"),
                                         ("amount", "=", 0)], limit=1)
pos_categ = env["pos.category"].search([("name", "=", "Platos")], limit=1) or env["pos.category"].create({"name": "Platos"})


def product(name, price, taxes, cost=0.0, pos=True, ptype="consu", supplier_taxes=None):
    tmpl = env["product.template"].search([("name", "=", name)], limit=1)
    vals = {"name": name, "list_price": price, "standard_price": cost, "type": ptype,
            "taxes_id": [(6, 0, taxes.ids)],
            "supplier_taxes_id": [(6, 0, (purchase_tax if supplier_taxes is None else supplier_taxes).ids)],
            "available_in_pos": pos, "pos_categ_ids": [(6, 0, pos_categ.ids)] if pos else []}
    return tmpl.write(vals) and tmpl if tmpl else env["product.template"].create(vals)


product("Pollo al horno", 350.0, sale_tax, 140.0)
product("Mofongo de chicharron", 425.0, sale_tax, 160.0)
product("Jugo natural", 120.0, sale_tax, 35.0)
product("Habichuelas con dulce", 150.0, sale_tax, 50.0)
product("Servicio de catering para exportacion", 1000.0, exempt_sale or sale_tax, pos=False, ptype="service")
product("Platanos (compra a productor)", 25.0, env["account.tax"], 0.0, pos=False, supplier_taxes=env["account.tax"])
product("Hielo y desechables (gasto menor)", 450.0, env["account.tax"], 0.0, pos=False, supplier_taxes=env["account.tax"])
product("Licencia de software (servicio del exterior)", 5900.0, env["account.tax"], 0.0, pos=False, ptype="service", supplier_taxes=env["account.tax"])

# POS restaurant: presets dine-in (ITBIS + legal tip) / takeout (ITBIS only)
env["pos.preset"]._l10n_do_apply_restaurant_fiscal_positions(company)
pos = env["pos.config"].search([("module_pos_restaurant", "=", True)], limit=1)
if not pos:
    pos = env["pos.config"].create({"name": "Chefalitas Restaurante", "module_pos_restaurant": True})
pos.write({"name": "Chefalitas Restaurante"})
# presets: Dine In (default, ITBIS + propina legal); Takeout and Delivery (ITBIS only, no tip)
presets = env["pos.preset"]
for xmlid in ("pos_restaurant.pos_takein_preset", "pos_restaurant.pos_takeout_preset", "pos_restaurant.pos_delivery_preset"):
    presets |= env.ref(xmlid, raise_if_not_found=False) or env["pos.preset"]
pos.write({"use_presets": True, "default_preset_id": presets[:1].id, "available_preset_ids": [(6, 0, presets.ids)]})
# floor with 4 tables
floor = env["restaurant.floor"].search([("name", "=", "Salon principal")], limit=1) or env["restaurant.floor"].create(
    {"name": "Salon principal", "pos_config_ids": [(4, pos.id)]})
for number in range(1, 5):
    if not floor.table_ids.filtered(lambda t, n=number: t.table_number == n):
        env["restaurant.table"].create({"floor_id": floor.id, "table_number": number, "seats": 4})
print("floor:", floor.name, sorted(floor.table_ids.mapped("table_number")))
print("POS:", pos.name, "presets:", [(p.name, p.fiscal_position_id.name) for p in env["pos.preset"].search([])])
print("taxes:", sale_tax.name, "|", exempt_sale.name if exempt_sale else None, "| purchase:", purchase_tax.name)
env.cr.commit()
print("SETUP OK")
