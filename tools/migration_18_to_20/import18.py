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


# ------------------------------------------------------------------------------------------------ accounting
def import_accounts():
    """Accounts by code, taxes by (use, rate, name), journals by code. Missing ones are created with the same code."""
    st = stats_for("account.account")
    for a in rows("select a.id, a.code_store->>'1' as code, a.name, a.account_type, a.reconcile from account_account a "
                  "where a.id in (select distinct account_id from account_move_line)"):
        if target("account.account", "account_account", a["id"]):
            st["linked_or_existing"] += 1
            continue
        rec = env["account.account"].search([("code", "=", a["code"])], limit=1)
        if rec:
            remember(rec, "account_account", a["id"])
            st["linked_or_existing"] += 1
        else:
            upsert("account.account", "account_account", a["id"], {
                "code": a["code"], "name": tr(a["name"]), "account_type": a["account_type"], "reconcile": a["reconcile"]}, st)
    st = stats_for("account.tax")
    for t in rows("select id, type_tax_use, amount, name from account_tax"):
        if target("account.tax", "account_tax", t["id"]):
            st["linked_or_existing"] += 1
            continue
        rec = env["account.tax"].with_context(active_test=False).search([
            ("type_tax_use", "=", t["type_tax_use"]), ("amount", "=", float(t["amount"])), ("name", "=", tr(t["name"]))], limit=1)
        if rec:
            remember(rec, "account_tax", t["id"])
            st["linked_or_existing"] += 1
        else:
            st.setdefault("unmapped", []).append(tr(t["name"]))
    st = stats_for("account.journal")
    for j in rows("select j.*, a.code_store->>'1' as account_code from account_journal j "
                  "left join account_account a on a.id = j.default_account_id order by j.id"):
        if target("account.journal", "account_journal", j["id"]):
            st["linked_or_existing"] += 1
            continue
        rec = env["account.journal"].search([("code", "=", j["code"])], limit=1)
        if rec:
            remember(rec, "account_journal", j["id"])
            st["linked_or_existing"] += 1
            continue
        vals = {"name": tr(j["name"]), "code": j["code"], "type": j["type"]}
        if j["account_code"]:
            vals["default_account_id"] = target("account.account", "account_account", j["default_account_id"]).id or \
                env["account.account"].search([("code", "=", j["account_code"])], limit=1).id
        upsert("account.journal", "account_journal", j["id"], vals, st)
    # products were imported before the taxes were mapped: set their sale taxes now
    tax_rel = {}
    for r in rows("select prod_id, tax_id from product_taxes_rel"):
        tax_rel.setdefault(r["prod_id"], []).append(r["tax_id"])
    for tmpl_id, tax_ids in tax_rel.items():
        tmpl = target("product.template", "product_template", tmpl_id)
        if tmpl:
            tmpl.taxes_id = [(6, 0, [x.id for x in (target("account.tax", "account_tax", i) for i in tax_ids) if x])]


def _repartition(tax, src_line):
    """Tax line -> the matching repartition line of the mapped tax (invoice or refund, 'tax' type)."""
    lines = tax.refund_repartition_line_ids if src_line["refund"] else tax.invoice_repartition_line_ids
    return lines.filtered(lambda r: r.repartition_type == "tax")[:1]


MOVE_LINE_SQL = """
select l.*, coalesce(r.document_type = 'refund', false) as refund,
       array(select account_tax_id from account_move_line_account_tax_rel where account_move_line_id = l.id) as tax_ids
from account_move_line l left join account_tax_repartition_line r on r.id = l.tax_repartition_line_id
where l.move_id = %s order by l.id"""


def import_moves():
    """Every journal entry and invoice, same name, dates, amounts and NCF. Posted ones are posted again in Odoo 20
    without any e-CF sending (EasyCount stays disabled on the company)."""
    st = stats_for("account.move")
    doc_prefix = {r["id"]: r["doc_code_prefix"] for r in rows("select id, doc_code_prefix from l10n_latam_document_type")}
    ctx = {"check_move_validity": False, "skip_invoice_sync": True, "skip_account_move_synchronization": True,
           "tracking_disable": True, "mail_notrack": True, "mail_create_nolog": True}
    Move = env["account.move"].sudo().with_context(**ctx)
    done = 0
    for m in rows("select * from account_move order by date, id"):
        if target("account.move", "account_move", m["id"]):
            st["linked_or_existing"] += 1
            continue
        line_vals = []
        for l in rows(MOVE_LINE_SQL, (m["id"],)):
            if l["display_type"] in ("line_section", "line_note"):
                line_vals.append((0, 0, {"display_type": l["display_type"], "name": l["name"] or "-"}))
                continue
            vals = {
                "display_type": l["display_type"] or "product",
                "account_id": target("account.account", "account_account", l["account_id"]).id,
                "partner_id": target("res.partner", "res_partner", l["partner_id"]).id or False,
                "name": l["name"], "debit": float(l["debit"] or 0), "credit": float(l["credit"] or 0),
                "date_maturity": l["date_maturity"],
                "tax_ids": [(6, 0, [x.id for x in (target("account.tax", "account_tax", i) for i in l["tax_ids"]) if x])],
            }
            if l["product_id"]:
                vals["product_id"] = target("product.product", "product_product", l["product_id"]).id or False
            if l["display_type"] == "product" and m["move_type"] != "entry":
                vals.update(quantity=float(l["quantity"] or 0), price_unit=float(l["price_unit"] or 0),
                             discount=float(l["discount"] or 0))
            if l["tax_line_id"]:
                tax = target("account.tax", "account_tax", l["tax_line_id"])
                vals["tax_repartition_line_id"] = _repartition(tax, l).id
            line_vals.append((0, 0, vals))
        vals = {
            "move_type": m["move_type"], "date": m["date"], "invoice_date": m["invoice_date"],
            "invoice_date_due": m["invoice_date_due"], "ref": m["ref"],
            "journal_id": target("account.journal", "account_journal", m["journal_id"]).id,
            "partner_id": target("res.partner", "res_partner", m["partner_id"]).id or False,
            "narration": m["narration"], "line_ids": line_vals,
        }
        if m["l10n_latam_document_type_id"]:
            vals["l10n_latam_document_type_id"] = env["l10n_latam.document.type"].search(
                [("doc_code_prefix", "=", doc_prefix[m["l10n_latam_document_type_id"]]), ("country_id.code", "=", "DO")], limit=1).id
            if m["name"] and m["name"] != "/":  # drafts have no NCF yet
                vals["l10n_latam_document_number"] = m["name"]
        move = Move.create(vals)
        remember(move, "account_move", m["id"])
        if m["state"] == "posted":
            try:
                with env.cr.savepoint():
                    move._post(soft=False)
            except Exception as exc:  # noqa: BLE001 - recorded and posted below without business checks
                st.setdefault("post_fallback", []).append(f"{m['name']}: {str(exc).splitlines()[0][:120]}")
                env.cr.execute("UPDATE account_move SET state='posted' WHERE id=%s", [move.id])
                env.cr.execute("UPDATE account_move_line SET parent_state='posted' WHERE move_id=%s", [move.id])
        elif m["state"] == "cancel":
            move.button_cancel()
        if move.name != m["name"] and m["name"] not in ("/", None):
            env.cr.execute("UPDATE account_move SET name=%s WHERE id=%s", [m["name"], move.id])  # keep the historical name
            st["renamed"] = st.get("renamed", 0) + 1
        st["created"] += 1
        done += 1
        if done % 200 == 0:
            env.cr.commit()
    if "post_fallback" in st:
        st["post_fallback_count"] = len(st["post_fallback"])
        st["post_fallback"] = st["post_fallback"][:10]


def import_reconcile():
    """Reconcile the same journal items as in Odoo 18, group by group (full reconcile, or a lone partial).
    Source and target lines of a move were created in the same order, so a line maps by its position."""
    st = stats_for("account.reconcile")
    src_lines = {}
    for r in rows("select id, move_id from account_move_line order by move_id, id"):
        src_lines.setdefault(r["move_id"], []).append(r["id"])
    position = {lid: (mid, i) for mid, ids in src_lines.items() for i, lid in enumerate(ids)}
    target_lines = {}

    def line(src_line_id):
        mid, i = position[src_line_id]
        if mid not in target_lines:
            move = target("account.move", "account_move", mid)
            lines = move.line_ids.sorted("id")
            if len(lines) != len(src_lines[mid]):
                raise ValueError(f"move {mid}: {len(src_lines[mid])} source lines, {len(lines)} target lines")
            target_lines[mid] = lines
        return target_lines[mid][i]

    groups = {}
    for p in rows("select id, debit_move_id, credit_move_id, full_reconcile_id from account_partial_reconcile order by id"):
        groups.setdefault(p["full_reconcile_id"] or f"p{p['id']}", set()).update((p["debit_move_id"], p["credit_move_id"]))
    for key, ids in groups.items():
        lines = env["account.move.line"].browse([line(i).id for i in ids])
        if all(l.reconciled for l in lines) or lines.matched_debit_ids or lines.matched_credit_ids:
            st["linked_or_existing"] += 1
            continue
        try:
            with env.cr.savepoint():
                lines.with_context(no_exchange_difference=True).reconcile()
            st["created"] += 1
        except Exception as exc:  # noqa: BLE001 - reported, the rest continues
            st.setdefault("failed", []).append(f"{key}: {str(exc).splitlines()[0][:120]}")
    if "failed" in st:
        st["failed_count"] = len(st["failed"])
        st["failed"] = st["failed"][:10]


PHASE_STEPS = {
    "master": [import_company, import_partners, import_uoms, import_categories, import_products, import_combos],
    "accounts": [import_accounts],
    "moves": [import_moves],
    "reconcile": [import_reconcile],
}

for phase in PHASES:
    for step in PHASE_STEPS[phase]:
        step()
        env.cr.commit()
print("IMPORT18_REPORT " + json.dumps(REPORT, default=str, ensure_ascii=False))
