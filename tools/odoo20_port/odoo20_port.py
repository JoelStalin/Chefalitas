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


def search_groups(s):
    """Search views: Odoo 20 group-by filters sit in a bare <group> (no expand/string)."""
    return re.sub(r'<group\s+expand="[01]"(?:\s+string="[^"]*")?\s*>|<group\s+string="[^"]*"\s+expand="[01]"\s*>',
                  "<group>", s)


def xml(s, path):
    s = attrs(s, path)
    s = groups(s, path)
    s = list_views(s)
    s = search_groups(s)
    s = s.replace('<field name="users" eval=', '<field name="user_ids" eval=')
    s = s.replace('<field name="groups_id" eval=', '<field name="group_ids" eval=')
    return s


def sql_constraints(s, path):
    """_sql_constraints = [(name, definition, message), ...] -> _name = models.Constraint(...).
    Odoo 20 ignores _sql_constraints (only logs a warning), so constraints silently vanish."""
    import ast

    def repl(m):
        indent, body = m.group(1), m.group(2)
        try:
            items = ast.literal_eval("[" + body + "]")
        except Exception:
            report.append(f"{os.path.relpath(path, addon)}: _sql_constraints not literal, port by hand")
            return m.group(0)
        if not all(isinstance(t, tuple) and len(t) == 3 and all(isinstance(x, str) for x in t) for t in items):
            report.append(f"{os.path.relpath(path, addon)}: _sql_constraints with translated/odd messages, port by hand")
            return m.group(0)
        out = []
        for name, definition, message in items:
            attr = name if name.startswith("_") else "_" + name
            out.append(f"{indent}{attr} = models.Constraint(\n{indent}    {definition!r},\n{indent}    {message!r},\n{indent})")
        return "\n".join(out) + "\n"

    return re.sub(r"^([ \t]+)_sql_constraints\s*=\s*\[(.*?)^\1\]\s*\n", repl, s, flags=re.S | re.M)


def py(s, path):
    s = sql_constraints(s, path)
    # @route(type='json') is a deprecated alias of type='jsonrpc' since 19.0
    s = re.sub(r"""(@http\.route\([^)]*type\s*=\s*)(["'])json\2""", r"\1\2jsonrpc\2", s)
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


def ir_rules_to_access():
    """Odoo 20 removed ir.rule: record rules are ir.access rows with a domain.
    A rule without groups becomes a global restriction (empty group_id)."""
    import csv
    import io
    rows = []
    for d, _, files in os.walk(addon):
        for f in files:
            if not f.endswith(".xml"):
                continue
            path = os.path.join(d, f)
            raw = open(path, "rb").read()
            crlf = b"\r\n" in raw
            s = raw.decode("utf-8").replace("\r\n", "\n")
            recs = list(re.finditer(r'[ \t]*<record id="([^"]+)" model="ir\.rule">(.*?)</record>\n?', s, re.S))
            if not recs:
                continue
            for m in recs:
                rid, body = m.group(1), m.group(2)
                fld = lambda n: re.search(rf'<field name="{n}"[^>]*?(?:ref="([^"]+)"|eval="([^"]+)"|>([^<]*)</field>)', body)  # noqa: E731
                name = (fld("name") or [None, None, None, rid]).group(3) or rid
                model_ref = fld("model_id").group(1)
                model_key = model_ref.split(".")[-1].removeprefix("model_")
                model = names.get(model_key) or model_key.replace("_", ".")
                dom_m = fld("domain_force")
                domain = (dom_m.group(3) or dom_m.group(2) or "").strip() if dom_m else ""
                grp_m = re.search(r"""<field name="groups" eval="\[([^\]]*)\]"/>""", body)
                groups = re.findall(r"ref\('([^']+)'\)", grp_m.group(1)) if grp_m else [""]
                op = ""
                for letter, perm in (("c", "perm_create"), ("r", "perm_read"), ("u", "perm_write"), ("d", "perm_unlink")):
                    pm = re.search(rf'<field name="{perm}" eval="(\w+)"', body)
                    if not pm or pm.group(1) in ("True", "1"):
                        op += letter
                for g in groups:
                    rows.append([rid if len(groups) == 1 else f"{rid}_{g.split('.')[-1]}", name.strip(), model, g, op, domain])
            for m in reversed(recs):
                s = s[:m.start()] + s[m.end():]
            open(path, "wb").write((s.replace("\n", "\r\n") if crlf else s).encode("utf-8"))
            print("ported", os.path.relpath(path, addon), "(ir.rule -> ir.access)")
    if rows:
        csv_path = os.path.join(addon, "security", "ir.access.csv")
        out = io.StringIO()
        w = csv.writer(out, lineterminator="\n")
        if not os.path.exists(csv_path):
            w.writerow(["id", "name", "model_id", "group_id/id", "operation", "domain"])
        for r in rows:
            w.writerow(r)
        with open(csv_path, "a", encoding="utf-8") as fh:
            fh.write(out.getvalue())
        print(f"ir.access.csv: +{len(rows)} rule rows")


names = {}
for root in [addon] + extra:
    for d, _, files in os.walk(root):
        for f in files:
            if f.endswith(".py"):
                t = open(os.path.join(d, f), encoding="utf-8", errors="ignore").read()
                for mm in re.finditer(r"""_name\s*=\s*['"]([\w.]+)['"]""", t):
                    names[mm.group(1).replace(".", "_")] = mm.group(1)

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

ir_rules_to_access()

print("\nMANUAL REVIEW NEEDED:" if report else "\nno manual items detected")
for r in report:
    print(" -", r)
