"""Issues one e-CF of every DGII type from Odoo 20 through EasyCount (run inside `odoo shell -d ecflive`).

Sales E31, E32 (< and >= DOP250k), E44, E45, E46; notes E33 (debit) and E34 (credit, reversal of the E31);
buyer-issued vendor bills E41, E43, E47. Each move is posted, which makes EasyCount assign the e-NCF and send it
to the DGII environment EasyCount runs against (DGII_ENV). Prints e-NCF, DGII status and TrackId per document;
a rejection is reported and the run continues with the next type. TYPES="E46,E41" limits the run to those types.
"""
import os

from odoo.exceptions import UserError

env = env  # noqa: F821 - provided by odoo shell
company = env.company
Doc = env["l10n_latam.document.type"]
Partner = env["res.partner"]
Product = env["product.product"]
sale_journal = env["account.journal"].search([("type", "=", "sale"), ("company_id", "=", company.id)], limit=1)
purchase_journal = env["account.journal"].search([("type", "=", "purchase"), ("company_id", "=", company.id)], limit=1)


def doc(code):
    return Doc.search([("doc_code_prefix", "=", code), ("country_id.code", "=", "DO")], limit=1)


def partner(name):
    return Partner.search([("name", "=", name)], limit=1)


def product(name):
    return Product.search([("name", "=", name)], limit=1)


def make(code, move_type, partner_name, lines, **extra):
    journal = sale_journal if move_type.startswith("out") else purchase_journal
    move = env["account.move"].create({
        "move_type": move_type, "journal_id": journal.id, "partner_id": partner(partner_name).id,
        "l10n_latam_document_type_id": doc(code).id, "invoice_date": env.cr.now().date(),
        "invoice_line_ids": [(0, 0, {"product_id": product(p).id, "quantity": q, **({"price_unit": pu} if pu else {})})
                             for p, q, pu in lines],
        **extra,
    })
    return move


results = []
WANT = {t.strip() for t in os.environ.get("TYPES", "").split(",") if t.strip()}


def post(label, move):
    if WANT and label.split()[0] not in WANT:
        move.unlink()
        return move
    try:
        with env.cr.savepoint():
            move.action_post()
        results.append((label, move.l10n_do_fiscal_number, move.l10n_do_easycount_status, move.l10n_do_easycount_track_id, ""))
    except UserError as exc:
        results.append((label, move.l10n_do_fiscal_number, "ERROR", None, str(exc).replace("\n", " ")[:300]))
    env.cr.commit()
    return move


e31 = post("E31 credito fiscal", make("E31", "out_invoice", "ITERATIVO SRL", [("Pollo al horno", 2, 0), ("Jugo natural", 2, 0)]))
post("E32 consumo < 250k (RFCE)", make("E32", "out_invoice", "CONSUMIDOR FINAL", [("Mofongo de chicharron", 1, 0)]))
post("E32 consumo >= 250k", make("E32", "out_invoice", "JOSE LUIS LOPEZ", [("Pollo al horno", 800, 0)]))
post("E44 regimen especial", make("E44", "out_invoice", "ZONA FRANCA INDUSTRIAL DE LAS AMERICAS", [("Servicio de catering para exportacion", 2, 0)]))
post("E45 gubernamental", make("E45", "out_invoice", "MINISTERIO DE INDUSTRIA Y COMERCIO", [("Pollo al horno", 10, 0)]))
post("E46 exportacion", make("E46", "out_invoice", "BLUE OCEAN IMPORTS LLC", [("Servicio de catering para exportacion", 3, 0)]))
if e31.exists() and e31.l10n_do_fiscal_number and e31.state == "posted":
    post("E33 nota de debito", make("E33", "out_invoice", "ITERATIVO SRL", [("Jugo natural", 1, 0)],
                                    l10n_do_origin_ncf=e31.l10n_do_fiscal_number, l10n_do_ecf_modification_code="3"))
    refund = make("E34", "out_refund", "ITERATIVO SRL", [("Jugo natural", 1, 0)],
                  reversed_entry_id=e31.id, l10n_do_origin_ncf=e31.l10n_do_fiscal_number, l10n_do_ecf_modification_code="3")
    post("E34 nota de credito", refund)
post("E41 compras (proveedor informal)", make("E41", "in_invoice", "JOSE LUIS LOPEZ", [("Platanos (compra a productor)", 40, 25.0)]))
post("E43 gastos menores", make("E43", "in_invoice", "FERRETERIA EL CHINO (gasto menor)", [("Hielo y desechables (gasto menor)", 1, 450.0)]))
post("E47 pagos al exterior", make("E47", "in_invoice", "CLOUD SOFTWARE INC", [("Licencia de software (servicio del exterior)", 1, 5900.0)]))

print("=" * 100)
for label, encf, status, track, err in results:
    print(f"{label:34} {encf or '-':15} {status or '-':22} {track or ''} {err}")
ok = sum(1 for r in results if r[2] in ("Aceptado", "Aceptado Condicional"))
print(f"{ok}/{len(results)} aceptados por la DGII")
