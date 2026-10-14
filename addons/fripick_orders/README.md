# fripick-odoo-addons

Odoo 20 addons for Fripick restaurants. Author GetUpSoft, LGPL-3.

## fripick_orders

| Feature | How |
|---|---|
| Capture closed orders per company | `pos.order.action_pos_order_paid` creates a `fripick.order` with lines and preparation notes (once per order). |
| Kitchen ticket (comanda) | ESC/POS 80 mm ticket with order, time, table, items and preparation, queued to the company's kitchen printer. |
| Cashier labels | Optional per company (`Imprimir etiquetas Fripick en caja`): Fripick 80 mm format, or standard A4 (QWeb PDF). |
| Printing | `direct`: Odoo on the same network sends raw ESC/POS to IP:9100. `agent`: POS Printing Suite local agent (HTTP). `gateway`: Odoo in the cloud; the downloadable gateway pulls jobs with the printer token (no inbound port). Failed jobs retry every 2 minutes, up to 5 attempts. |
| Gateway download | Printer form > *Descargar gateway* (`/fripick/gateway/download`): `fripick_gateway.py` (stdlib) + installers for Windows (scheduled task as SYSTEM), macOS (launchd) and Android tablets (Termux + Termux:Boot). |
| Daily company sync | Cron reads a JSON feed (`fripick.sync_url`, `fripick.sync_token`) and updates companies matched by Fripick ID or RNC. It never creates companies (accounting decision). |
| Monthly invoice | Cron runs daily and acts on day 1: one invoice per company for last month's orders. Flag `Quién emite la factura mensual`: *la empresa* invoices the Fripick contact, or *Fripick* (company in `fripick.company_id`) invoices the restaurant. Posting assigns the fiscal voucher (e-CF via `l10n_do_accounting` when installed); if posting fails, the draft stays for review. |

Depends on `point_of_sale`, `account`, `pos_printing_suite`. Tests: `--test-tags /fripick_orders` (8 tests).

### Assumptions to confirm

- Monthly invoice amount = sum of last month's captured orders. If Fripick charges a commission or a fee, the
  line price changes; tell us the rule.
- Fripick has no official API: the company feed is to be produced by an ORCA scraper and published as JSON for
  this cron. Pending: the Fripick portal URL and credentials (not found in any `.env.local`).

### Findings

- The workspace rule requires `OrcaAuditMixin` on tracked models, but no addon in this tree defines it yet
  (`orca_bridge` has no mixin). Audit logging is pending until the mixin exists.
- Odoo 20 changes handled: `ir.access` instead of `ir.model.access`, `models.Constraint` instead of
  `_sql_constraints`, typed `get_str`/`get_int` for system parameters, read-only GET and `auth="none"` routes
  (`readonly=False` where the route writes), `Binary` requires `BinaryValue` (payload stored as base64 text).

