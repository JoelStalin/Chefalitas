"""List xpath/field anchors of an addon's inherited views that do not exist in the Odoo 20 parent.

Run inside an Odoo image with the addons mounted:
  python3 check_view_anchors.py <module_dir> [<extra addons root> ...]
The parent arch is taken raw from its XML file (other inheriting views are NOT applied), so a
MISS can be a false positive when the anchor is added by another module; review those by hand.
"""
import glob
import os
import sys

from lxml import etree

ODOO_ADDONS = ["/usr/lib/python3/dist-packages/odoo/addons"]
mod = sys.argv[1].rstrip("/")
roots = ODOO_ADDONS + sys.argv[2:]


def find_record(xmlid):
    module, rid = xmlid.split(".", 1)
    for root in roots:
        for f in glob.glob(os.path.join(root, module, "**", "*.xml"), recursive=True):
            try:
                tree = etree.parse(f)
            except Exception:
                continue
            for rec in tree.xpath(f"//record[@id='{rid}'] | //template[@id='{rid}']"):
                arch = rec.xpath("field[@name='arch']")
                return (arch[0] if arch else rec), f
    return None, None


def spec_expr(spec):
    if spec.tag == "xpath":
        return spec.get("expr")
    if spec.tag == "field":
        return f"//field[@name='{spec.get('name')}']"
    attrs = " and ".join(f"@{k}='{v}'" for k, v in spec.attrib.items() if k != "position")
    return f"//{spec.tag}[{attrs}]" if attrs else f"//{spec.tag}"


module_name = os.path.basename(mod)
misses = 0
for f in sorted(glob.glob(os.path.join(mod, "**", "*.xml"), recursive=True)):
    try:
        tree = etree.parse(f)
    except Exception as exc:
        print("XML ERROR", f, exc)
        continue
    for rec in tree.xpath("//record[field[@name='inherit_id']] | //template[@inherit_id]"):
        ref = rec.get("inherit_id") or rec.xpath("field[@name='inherit_id']")[0].get("ref")
        if "." not in ref:
            ref = f"{module_name}.{ref}"
        parent, pfile = find_record(ref)
        rid = rec.get("id")
        if parent is None:
            print(f"?    {os.path.relpath(f, mod)} {rid}: parent {ref} not found in sources")
            continue
        arch = rec.xpath("field[@name='arch']")
        specs = arch[0] if arch else rec
        for spec in specs:
            if not isinstance(spec.tag, str) or spec.tag in ("data",):
                continue
            expr = spec_expr(spec)
            try:
                hit = parent.xpath(expr)
            except Exception as exc:
                print(f"BAD  {os.path.relpath(f, mod)} {rid}: {expr} ({exc})")
                continue
            if not hit:
                misses += 1
                print(f"MISS {os.path.relpath(f, mod)} {rid} -> {ref}: {expr}")
print(f"{misses} anchors not found")
