"""Convert an Odoo <=19 security/ir.model.access.csv to the Odoo 20 security/ir.access.csv.

Odoo 20 replaced `ir.model.access` with `ir.access`:
    id,name,model_id,group_id/id,operation,domain
where model_id is the model *name* and operation is a subset of "crud".

Usage: port_access_csv_v20.py <module_dir> [<extra addons dir with model sources>...]
The model xmlid `model_foo_bar` is resolved by scanning `_name = "foo.bar"` in Python
sources, so ambiguous names (l10n_do_account_journal -> l10n_do.account.journal) are exact.
"""
import csv
import io
import os
import re
import sys

module = sys.argv[1]
search_roots = [module] + sys.argv[2:]
src = os.path.join(module, "security", "ir.model.access.csv")
dst = os.path.join(module, "security", "ir.access.csv")
manifest = os.path.join(module, "__manifest__.py")

names = {}
for root in search_roots:
    for d, _, files in os.walk(root):
        for f in files:
            if f.endswith(".py"):
                text = open(os.path.join(d, f), encoding="utf-8", errors="ignore").read()
                for m in re.finditer(r"""_name\s*=\s*['"]([\w.]+)['"]""", text):
                    names[m.group(1).replace(".", "_")] = m.group(1)


def model_name(xmlid):
    key = xmlid.split(".")[-1]
    key = key[len("model_"):] if key.startswith("model_") else key
    if key in names:
        return names[key]
    raise SystemExit(f"cannot resolve model for {xmlid!r}; pass the addons dir that defines it")


def flag(v):
    return str(v).strip() in ("1", "True", "true")


rows = list(csv.DictReader(open(src, encoding="utf-8")))
out = io.StringIO()
w = csv.writer(out, lineterminator="\n")
w.writerow(["id", "name", "model_id", "group_id/id", "operation", "domain"])
for r in rows:
    model_key = r.get("model_id:id") or r.get("model_id/id")
    group = r.get("group_id:id") or r.get("group_id/id") or ""
    op = "".join(letter for letter, col in (("c", "perm_create"), ("r", "perm_read"),
                                            ("u", "perm_write"), ("d", "perm_unlink")) if flag(r.get(col, 0)))
    if not op:
        continue  # an all-false line grants nothing
    w.writerow([r["id"], r["name"], model_name(model_key), group, op, ""])

open(dst, "w", encoding="utf-8").write(out.getvalue())
os.remove(src)
m = open(manifest, encoding="utf-8").read()
m2 = m.replace("security/ir.model.access.csv", "security/ir.access.csv")
if m2 != m:
    open(manifest, "w", encoding="utf-8").write(m2)
print(out.getvalue(), end="")
