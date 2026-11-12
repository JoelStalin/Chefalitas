# Port de addons a Odoo 20

Herramientas usadas para portar los addons de Chefalitas a Odoo 20, tomando como referencia el código oficial `odoo/odoo` rama `20.0`.

```bash
python3 tools/odoo20_port/odoo20_port.py addons/<modulo>      # reescrituras mecánicas + reporte manual
```

Reescribe de forma segura:
- versión del manifest a `20.0.x`;
- `ir.model.access.csv` → `ir.access.csv`;
- `users`/`groups_id` → `user_ids`/`group_ids`;
- `attrs` simples → atributo directo;
- `<tree>` → `<list>`;
- grupos ocultos sin `category_id`.

Conserva CRLF. Lo que no puede convertir sin riesgo lo **reporta** en lugar de adivinarlo.

## Cambios de API de Odoo 20 encontrados (y cómo se resolvieron)

| Antes (≤18) | Odoo 20 |
|---|---|
| `ir.model.access` | `ir.access` (`operation` = subconjunto de `crud`) |
| `_sql_constraints` | `models.Constraint` (20 **ignora** `_sql_constraints` con un warning) |
| `odoo.osv.expression` | `odoo.fields.Domain` |
| `_name_search` | `_search_display_name(operator, value)` |
| `_get_last_sequence_domain` → `(where, params)` | devuelve `SQL`; consultas con `odoo.models.Query` |
| `Binary` en base64 | `BinaryBytes(data, filename)` / `.content` |
| `get_module_resource` | `odoo.tools.file_path` |
| `res.groups.users` / `category_id` | `user_ids` / `privilege_id` (`res.groups.privilege`) |
| `uom.category` | eliminado: `relative_uom_id` + `_has_common_reference` |
| `<report>` | `ir.actions.report` (sin `report_file`) |
| `currency._get_rates()` → número | `{id: (rate, date)}`: usar `_get_conversion_rate` |
| `from odoo.tests.common import Form` | `from odoo.tests import Form`; tests con `setup_country('xx')` |
| layouts de reporte por estilo | una sola plantilla `web.company_address_list` |

## Pruebas

`scripts` del ThinkCentre: `~/run_odoo_tests_etapa1.sh odoo:20.0 /<modulo> <modulo>` levanta una red y una base desechables (`etapa1-*`), instala el módulo, ejecuta sus pruebas y lo borra todo al final.
