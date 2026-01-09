    ARG ODOO_IMAGE=odoo:18.0
FROM ${ODOO_IMAGE}

USER root

# Patch lang url_code to avoid duplicate 'es' during base module load.
RUN python - <<'PY'
import pathlib
import re
import sys

path = pathlib.Path(
    "/usr/lib/python3/dist-packages/odoo/addons/base/data/res_lang_data.xml"
)
text = path.read_text(encoding="utf-8")
pattern = (
    r'(<record id="base.lang_es_419"[^>]*>.*?<field name="url_code">)'
    r'([^<]*)'
    r'(</field>)'
)
match = re.search(pattern, text, flags=re.S)
if not match:
    sys.stderr.write("base.lang_es_419 url_code not found in res_lang_data.xml\n")
    sys.exit(1)
if match.group(2) != "es-419":
    text = re.sub(pattern, r"\1es-419\3", text, flags=re.S)
    path.write_text(text, encoding="utf-8")
PY

USER odoo
