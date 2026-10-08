"""Chefalitas Odoo 18 -> Odoo 20: import into a fresh Odoo 20 database (decided 2026-10-08: new DB + import).

Run inside the Odoo 20 container:
    SRC_DSN="host=chefmig-src-pg dbname=chefalitas_src user=odoo password=..." PHASES=master \
        odoo shell -d chef20 --no-http < import18.py
Idempotent: every imported record gets the external id __import18__.<table>_<id>; reruns skip what exists.
Source records that carry a standard external id existing in Odoo 20 (uom, base category, company...) are linked,
not copied. The source is read-only. e-CF sending to EasyCount stays disabled during the import.
"""
import json
import os

import psycopg2
import psycopg2.extras

MOD = "__import18__"
SRC = psycopg2.connect(os.environ["SRC_DSN"])
SRC.set_session(readonly=True)
PHASES = os.environ.get("PHASES", "master").split(",")
IMD = env["ir.model.data"].sudo()  # noqa: F821 - provided by odoo shell
REPORT = {}


def rows(sql, args=None):
    with SRC.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, args)
        return cur.fetchall()


def tr(value):
    """Odoo jsonb translations -> one string (Spanish first)."""
    if isinstance(value, dict):
        for lang in ("es_DO", "es_419", "es_ES", "en_US"):
            if value.get(lang):
                return value[lang]
        return next(iter(value.values()), "")
    return value or ""


SRC_XMLID = {}


def src_xmlid(model, res_id):
    if model not in SRC_XMLID:
        SRC_XMLID[model] = {r["res_id"]: f'{r["module"]}.{r["name"]}' for r in rows(
            "select module, name, res_id from ir_model_data where model=%s and module <> %s", (model, MOD))}
    return SRC_XMLID[model].get(res_id)


def target(model, table, src_id):
    """Target record for a source id: imported before, or a standard record with the same external id."""
    if not src_id:
        return env[model]
    rec = env.ref(f"{MOD}.{table}_{src_id}", raise_if_not_found=False)
    if rec:
        return rec
    xid = src_xmlid(model, src_id)
    if xid:
        rec = env.ref(xid, raise_if_not_found=False)
        if rec and rec._name == model:
            return rec
    return env[model]


def remember(rec, table, src_id):
    IMD.create({"module": MOD, "name": f"{table}_{src_id}", "model": rec._name, "res_id": rec.id, "noupdate": True})


def remember_if_missing(rec, table, src_id):
    if not env.ref(f"{MOD}.{table}_{src_id}", raise_if_not_found=False):
        remember(rec, table, src_id)


def stats_for(name):
    return REPORT.setdefault(name, {"created": 0, "linked_or_existing": 0})


def upsert(model, table, src_id, vals, st):
    rec = target(model, table, src_id)
    if rec:
        st["linked_or_existing"] += 1
        return rec
    rec = env[model].sudo().create(vals)
    remember(rec, table, src_id)
    st["created"] += 1
    return rec


# ------------------------------------------------------------------------------------------------ master data
def import_company():
    c = rows("select c.*, p.vat, p.street, p.city, p.zip from res_company c "
             "join res_partner p on p.id = c.partner_id where c.id = 1")[0]
    company = env.company
    company.write({"name": c["name"], "vat": c["vat"], "street": c["street"], "city": c["city"],
                   "email": c["email"], "phone": c["phone"], "l10n_do_easycount_enabled": False})
    remember_if_missing(company.partner_id, "res_partner", c["partner_id"])
    REPORT["company"] = {"name": company.name, "vat": company.vat, "easycount_enabled": company.l10n_do_easycount_enabled}


def import_partners():
    st = stats_for("res.partner")
    country = {r["id"]: r["code"] for r in rows("select id, code from res_country")}
    for p in rows("select * from res_partner order by parent_id nulls first, id"):  # companies before contacts
        if target("res.partner", "res_partner", p["id"]):
            st["linked_or_existing"] += 1
            continue
        vals = {k: p[k] for k in ("vat", "street", "street2", "zip", "city", "email", "phone", "ref",
                                  "website", "function", "is_company", "active", "comment") if p.get(k) is not None}
        vals["name"] = p["name"] or "(sin nombre)"
        if p.get("mobile") and not p.get("phone"):
            vals["phone"] = p["mobile"]
        if p.get("country_id"):
            vals["country_id"] = env["res.country"].search([("code", "=", country[p["country_id"]])], limit=1).id
        if p.get("parent_id"):
            vals["parent_id"] = target("res.partner", "res_partner", p["parent_id"]).id
        if p.get("l10n_do_dgii_tax_payer_type") and "l10n_do_dgii_tax_payer_type" in env["res.partner"]._fields:
            vals["l10n_do_dgii_tax_payer_type"] = p["l10n_do_dgii_tax_payer_type"]
        upsert("res.partner", "res_partner", p["id"], vals, st)


def import_uoms():
    st = stats_for("uom.uom")
    units = env.ref("uom.product_uom_unit")
    for u in rows("select id, name from uom_uom"):
        if target("uom.uom", "uom_uom", u["id"]):
            st["linked_or_existing"] += 1
            continue
        name = tr(u["name"])
        rec = env["uom.uom"].search([("name", "=ilike", name)], limit=1) or units
        remember(rec, "uom_uom", u["id"])
        st["linked_or_existing"] += 1
        if rec == units and name.lower() not in ("units", "unidades"):
            st.setdefault("mapped_to_units", []).append(name)


def import_categories():
    st = stats_for("product.category")
    for c in rows("select * from product_category order by parent_path"):
        upsert("product.category", "product_category", c["id"], {
            "name": c["name"], "parent_id": target("product.category", "product_category", c["parent_id"]).id}, st)
    st2 = stats_for("pos.category")
    for c in rows("select * from pos_category order by parent_id nulls first, id"):
        upsert("pos.category", "pos_category", c["id"], {
            "name": tr(c["name"]), "sequence": c["sequence"],
            "parent_id": target("pos.category", "pos_category", c["parent_id"]).id}, st2)


def import_products():
    _import_templates("type <> 'combo'")


def import_combos():
    """Combo products need their choices first: combos and items reference products imported above."""
    st = stats_for("product.combo")
    for c in rows("select * from product_combo order by id"):
        items = rows("select * from product_combo_item where combo_id = %s order by id", (c["id"],))
        upsert("product.combo", "product_combo", c["id"], {
            "name": c["name"], "sequence": c["sequence"],
            "combo_item_ids": [(0, 0, {"product_id": target("product.product", "product_product", i["product_id"]).id,
                                       "extra_price": float(i["extra_price"] or 0)}) for i in items],
        }, st)
    combos = {}
    for r in rows("select product_template_id, product_combo_id from product_combo_product_template_rel"):
        combos.setdefault(r["product_template_id"], []).append(r["product_combo_id"])
    _import_templates("type = 'combo'", extra=lambda t: {
        "combo_ids": [(6, 0, [target("product.combo", "product_combo", i).id for i in combos.get(t["id"], [])])]})


def _import_templates(where, extra=None):
    st = stats_for("product.template")
    pos_categs, taxes = {}, {}
    for r in rows("select product_template_id, pos_category_id from pos_category_product_template_rel"):
        pos_categs.setdefault(r["product_template_id"], []).append(r["pos_category_id"])
    for r in rows("select prod_id, tax_id from product_taxes_rel"):
        taxes.setdefault(r["prod_id"], []).append(r["tax_id"])
    pending_variants = []
    for t in rows(f"select * from product_template where {where} order by id"):
        if target("product.template", "product_template", t["id"]):
            st["linked_or_existing"] += 1
            continue
        variants = rows("select * from product_product where product_tmpl_id = %s order by id", (t["id"],))
        vals = {
            "name": tr(t["name"]) or "(sin nombre)",
            "type": t["type"] if t["type"] in ("consu", "service", "combo") else "consu",
            "is_storable": bool(t.get("is_storable")),
            "list_price": float(t["list_price"] or 0),
            "categ_id": target("product.category", "product_category", t["categ_id"]).id
            or env.ref("product.product_category_goods").id,
            "uom_id": target("uom.uom", "uom_uom", t["uom_id"]).id,
            "sale_ok": t["sale_ok"], "purchase_ok": t["purchase_ok"], "active": t["active"],
            "available_in_pos": bool(t.get("available_in_pos")), "to_weight": bool(t.get("to_weight")),
            "default_code": t["default_code"],
            "pos_categ_ids": [(6, 0, [target("pos.category", "pos_category", i).id for i in pos_categs.get(t["id"], [])])],
            "taxes_id": [(6, 0, [r.id for r in (target("account.tax", "account_tax", i) for i in taxes.get(t["id"], [])) if r])],
        }
        if extra:
            vals.update(extra(t))
        if len(variants) == 1:  # templates with attributes get their variants in a later phase
            v = variants[0]
            vals["barcode"] = v["barcode"]
            if isinstance(v["standard_price"], dict):
                vals["standard_price"] = float(v["standard_price"].get("1") or 0)
        tmpl = upsert("product.template", "product_template", t["id"], vals, st)
        if len(variants) == 1:
            remember_if_missing(tmpl.product_variant_id, "product_product", variants[0]["id"])
        else:
            pending_variants.append(t["id"])
    st["with_variants_pending"] = st.get("with_variants_pending", 0) + len(pending_variants)


PHASE_STEPS = {
    "master": [import_company, import_partners, import_uoms, import_categories, import_products, import_combos],
}

for phase in PHASES:
    for step in PHASE_STEPS[phase]:
        step()
        env.cr.commit()
print("IMPORT18_REPORT " + json.dumps(REPORT, default=str, ensure_ascii=False))
