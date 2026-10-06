"""Mechanical Odoo <=18 -> 20 port for one addon (reference: odoo/odoo 20.0 addons).

Safe, reviewable rewrites only; anything ambiguous is REPORTED, not guessed:
- __manifest__ version 18.0.x / 17.0.x / 1.0.0 -> 20.0.x
- security/ir.model.access.csv -> security/ir.access.csv (via port_access_csv_v20.py)
- res.groups "users" -> "user_ids"; res.users "groups_id" -> "group_ids" (py + xml)
- attrs="{'invisible': [('f','=',False)]}" style (single leaf) -> invisible="..."
- self._context -> self.env.context ; from odoo.tests.common import Form -> from odoo.tests import Form
Keeps CRLF files as CRLF.

Usage: odoo20_port.py <addon_dir> [extra model source dirs...]
"""
import os
import re
import subprocess
import sys

addon = sys.argv[1].rstrip("/")
extra = sys.argv[2:]
report = []


def rw(path, fn):
    raw = open(path, "rb").read()
    crlf = b"\r\n" in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    new = fn(s, path)
    if new != s:
        open(path, "wb").write((new.replace("\n", "\r\n") if crlf else new).encode("utf-8"))
        print("ported", os.path.relpath(path, addon))


def manifest(s, _):
    return re.sub(r"""(["']version["']\s*:\s*["'])(?:1[0-9]\.0\.|1\.0\.0)""",
                  lambda m: m.group(1) + ("20.0." if not m.group(0).endswith("1.0.0") else "20.0.1.0.0"),
                  s, count=1)


OPS = {"=": "==", "!=": "!="}


def _leaf_expr(field, op, value):
    if op in ("=", "==") and value == "False":
        return f"not {field}"
    if op in ("=", "==") and value == "True":
        return field
    if op in ("!=",) and value == "False":
        return field
    if op in ("in", "not in"):
        return f"{field} {op} {value}"
    if op in OPS:
        return f"{field} {OPS[op]} {value}"
    return None


def attrs(s, path):
    def repl(m):
        body = m.group(1)
        parts = re.findall(r"'(invisible|readonly|required)'\s*:\s*\[\s*\(\s*'([\w.]+)'\s*,\s*'([^']+)'\s*,\s*([^)]+?)\s*\)\s*\]", body)
        rebuilt = re.sub(r"\s", "", body)
        expect = "{" + ",".join(f"'{k}':[('{f}','{o}',{v.replace(' ', '')})]" for k, f, o, v in parts) + "}"
        if not parts or rebuilt != expect:
            report.append(f"{os.path.relpath(path, addon)}: manual attrs port needed: {m.group(0)[:120]}")
            return m.group(0)
        out = []
        for k, f, o, v in parts:
            e = _leaf_expr(f, o, v.strip())
            if e is None:
                report.append(f"{os.path.relpath(path, addon)}: manual attrs op {o}: {m.group(0)[:120]}")
                return m.group(0)
            out.append(f'{k}="{e}"')
        return " ".join(out)
    s = re.sub(r'''attrs="(\{[^"]*\})"''', repl, s)
    if re.search(r"\bstates=\"", s):
        report.append(f"{os.path.relpath(path, addon)}: 'states=' attribute needs manual port")
    return s


def groups(s, path):
    """res.groups.category_id is gone in Odoo 19+ (groups hang from res.groups.privilege).
    A hidden category simply means "no privilege"; any other category needs a privilege."""
    def repl(m):
        rec = m.group(0)
        rec = re.sub(r'\n?[ \t]*<field name="category_id" ref="base\.module_category_hidden"\s*/>', "", rec)
        if 'name="category_id"' in rec:
            report.append(f"{os.path.relpath(path, addon)}: res.groups category_id -> create res.groups.privilege "
                          f"and use privilege_id ({re.search(r'id=\"([^\"]+)\"', rec).group(1)})")
        return rec
    return re.sub(r'<record[^>]*model="res\.groups"[^>]*>.*?</record>', repl, s, flags=re.S)


def list_views(s):
    """<tree> views are <list> since Odoo 17/18; view_mode 'tree' -> 'list'."""
    s = re.sub(r"<tree(\s|>|/>)", r"<list\1", s)
    s = s.replace("</tree>", "</list>")
    s = re.sub(r'(<field name="view_mode">[^<]*)\btree\b', r"\1list", s)
    return s


def xml(s, path):
    s = attrs(s, path)
    s = groups(s, path)
    s = list_views(s)
    s = s.replace('<field name="users" eval=', '<field name="user_ids" eval=')
    s = s.replace('<field name="groups_id" eval=', '<field name="group_ids" eval=')
    return s


def py(s, path):
    s = s.replace("self._context", "self.env.context")
    s = s.replace("from odoo.tests.common import Form", "from odoo.tests import Form")
    s = re.sub(r"\.groups_id\b", ".group_ids", s)
    for pat, msg in ((r"odoo\.osv", "odoo.osv.expression -> odoo.fields.Domain"),
                     (r"_sql_constraints\s*=", "_sql_constraints -> models.Constraint (Odoo 20 ignores them)"),
                     (r"def _name_search", "_name_search -> _search_display_name"),
                     (r"get_module_resource", "get_module_resource -> odoo.tools.file_path"),
                     (r"_get_rates\(", "_get_rates returns {id: (rate, date)} -> _get_conversion_rate"),
                     (r"\.(get|set)_param\(", "ir.config_parameter get_param/set_param -> get_str/set_str (get_bool/int/float)"),
                     (r"auth=['\"]none['\"]", "auth='none' route: check token handling / sudo() exposure"),
                     (r"_get_last_sequence_domain", "_get_last_sequence_domain returns SQL in Odoo 20"),
                     (r"base64\.b64(en|de)code\([^)]*\b(datas|_file)\b", "Binary fields: BinaryBytes / .content")):
        if re.search(pat, s):
            report.append(f"{os.path.relpath(path, addon)}: {msg}")
    return s


mf = os.path.join(addon, "__manifest__.py")
rw(mf, manifest)
for d, _, files in os.walk(addon):
    if "__pycache__" in d or "/static/lib" in d:
        continue
    for f in files:
        p = os.path.join(d, f)
        if f.endswith(".xml"):
            rw(p, xml)
        elif f.endswith(".py") and f != "__manifest__.py":
            rw(p, py)

if os.path.exists(os.path.join(addon, "security", "ir.model.access.csv")):
    here = os.path.dirname(os.path.abspath(__file__))
    subprocess.run([sys.executable, os.path.join(here, "port_access_csv_v20.py"), addon, *extra],
                   check=True, stdout=subprocess.DEVNULL)
    print("ported security/ir.model.access.csv -> security/ir.access.csv")

print("\nMANUAL REVIEW NEEDED:" if report else "\nno manual items detected")
for r in report:
    print(" -", r)
