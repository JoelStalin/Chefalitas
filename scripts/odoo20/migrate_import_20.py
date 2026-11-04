# Se ejecuta dentro de `odoo shell` del Odoo 20 (variable `env`). Importa lo exportado de Odoo 18 sin duplicar.
# Compañía principal: se actualiza la compañía 1. Contactos: se reutiliza el que tenga el mismo RNC o el mismo nombre y correo.
# Usuarios: se crean por login con los grupos que existan en Odoo 20 y se copia su clave cifrada (entran con la misma clave).
import json

data = json.load(open("/tmp/odoo18-export.json"))
Partner = env["res.partner"].with_context(active_test=False)
Users = env["res.users"].with_context(active_test=False, no_reset_password=True)
stats = {"companias": 0, "contactos_nuevos": 0, "contactos_existentes": 0, "usuarios_nuevos": 0, "usuarios_existentes": 0}

def country(code):
    return env["res.country"].search([("code", "=", code)], limit=1).id if code else False

def partner_vals(p, parent):
    return {
        "name": p["name"] or "(sin nombre)", "vat": p.get("vat") or False, "email": p.get("email") or False,
        "phone": p.get("phone") or False, "street": p.get("street") or False, "street2": p.get("street2") or False,
        "city": p.get("city") or False, "zip": p.get("zip") or False, "is_company": bool(p.get("is_company")),
        "parent_id": parent or False, "type": p.get("type") or "contact", "active": p.get("active", True),
        "ref": p.get("ref") or False, "comment": p.get("comment") or False, "country_id": country(p.get("country")),
        "customer_rank": p.get("customer_rank") or 0, "supplier_rank": p.get("supplier_rank") or 0,
    }

old_partners = {p["id"]: p for p in (data.get("partners") or [])}
old_company_partner = {c["partner_id"] for c in (data.get("companies") or [])}
pmap = {}

# compañías: la primera es la compañía principal (id 1 en Odoo 20)
companies = data.get("companies") or []
cmap = {}
for i, c in enumerate(companies):
    p = old_partners.get(c["partner_id"], {})
    vals = {"name": c["name"], "vat": p.get("vat") or False, "email": p.get("email") or False, "phone": p.get("phone") or False,
            "street": p.get("street") or False, "city": p.get("city") or False, "country_id": country(p.get("country"))}
    if i == 0:
        comp = env["res.company"].browse(1)
        comp.write(vals)
    else:
        comp = env["res.company"].search([("name", "=", c["name"])], limit=1) or env["res.company"].create(vals)
    cmap[c["id"]] = comp.id
    pmap[c["partner_id"]] = comp.partner_id.id
    stats["companias"] += 1

for p in data.get("partners") or []:
    if p["id"] in pmap:
        continue
    parent = pmap.get(p.get("parent_id"))
    found = Partner.browse()
    if p.get("vat"):
        found = Partner.search([("vat", "=", p["vat"]), ("parent_id", "=", parent or False)], limit=1)
    if not found and p.get("email"):
        found = Partner.search([("name", "=", p["name"]), ("email", "=", p["email"])], limit=1)
    if found:
        stats["contactos_existentes"] += 1
    else:
        vals = partner_vals(p, parent)
        if p.get("company_id") in cmap:
            vals["company_id"] = cmap[p["company_id"]]
        found = Partner.create(vals)
        stats["contactos_nuevos"] += 1
    pmap[p["id"]] = found.id

for u in data.get("users") or []:
    user = Users.search([("login", "=", u["login"])], limit=1)
    groups = env["res.groups"]
    for xmlid in u.get("groups") or []:
        g = env.ref(xmlid, raise_if_not_found=False)
        if g and g._name == "res.groups":
            groups |= g
    companies_ids = [cmap[c] for c in (u.get("companies") or []) if c in cmap] or [1]
    vals = {"group_ids": [(6, 0, groups.ids)], "company_ids": [(6, 0, companies_ids)],
            "company_id": cmap.get(u.get("company_id"), companies_ids[0]), "active": u.get("active", True)}
    if user:
        user.write(vals)
        stats["usuarios_existentes"] += 1
    else:
        vals.update({"login": u["login"], "partner_id": pmap.get(u["partner_id"]) or False})
        if not vals["partner_id"]:
            vals["name"] = u["login"]
        user = Users.create(vals)
        stats["usuarios_nuevos"] += 1
    if u.get("password"):
        env.cr.execute("UPDATE res_users SET password = %s WHERE id = %s", (u["password"], user.id))

env.cr.commit()
print("MIGRACION", json.dumps(stats, ensure_ascii=False))
