# Chefalitas → Odoo 20: inventory of what is missing to issue e-CF on November 1, 2026

Survey of 2026-10-13. Goal: Chefalitas invoicing on **Odoo 20** with **electronic invoices (e-CF) in production through EasyCount** starting **2026-11-01**. 19 days left.

## 1. Current state (measured, not assumed)

| Piece | Where | State |
|---|---|---|
| Real production | DESKTOP-3RD2JRI (Chefalitas office), **Odoo 18**, DB `chefalitas` | ⚠️ tunnel `chefalitas-prod-wsl2` **Down**: `chefalitas.com.do` returns 530 |
| Certified backup | This PC `Documents\chefalitas_backups\migration_odoo20_20261005_171346` | ✅ Odoo 18, 2026-10-05, SHA256 verified (58 partners, 2,473 moves, 9,207 POS orders, 975 attachments) |
| Copy in Miami | `odoo18-odoo-1` (`chefalitas-odoo:19.0`), DB `chefalitas` | Older snapshot: 445 products, 9,207 POS (last 2026-04-06), invoices up to 2026-05-10 |
| Odoo 20 | ThinkCentre `ecflive-odoo-1`, DB `ecflive` | Only **test data** (15 partners, 16 products, 8 e-CF invoices) |
| Chefalitas DGII certification | Portal CerteCF | ✅ **Paso 15: Finalizado** (2026-10-09) |
| EasyCount (e-CF) | easycount.me, Miami | Chefalitas tenant with `env` **empty** (no production environment defined) |
| Last POS sale in production | — | 2026-04-06 → **check whether they still use Odoo for sales** or something else |

## 2. Missing items, by area (🔴 blocks Nov 1 · 🟠 needed that week · 🟢 can come after)

### A. DGII / e-CF in production (🔴 the critical path)
1. 🔴 **Become an "Emisor Electrónico" in production**: after the certification, submit the authorization in the OFV ("Solicitud para ser Emisor Electrónico") and wait for the DGII's answer. **Needs Chefalitas's OFV password** (pending since 2026-10-08).
2. 🔴 **Production e-NCF sequences** (E31 tax credit, E32 final consumer, E34 credit note, E33 debit note as applicable), requested in the OFV and loaded in Odoo 20 / EasyCount.
3. 🔴 **Chefalitas tenant in EasyCount → production environment** (`env` = production `eCF`, production DGII URLs), with the valid .p12 certificate (**check its expiry date**).
4. 🔴 **Odoo 20 ↔ EasyCount production**: `l10n_do_accounting` configured with the production EasyCount API token (`/odoo/v1`), end-to-end test with a real invoice (E32 under DOP 250k and E31).
5. 🟠 Printed representation (RI/PDF) for E31/E32/E34 in Odoo 20, with the QR and security code (formats already worked out for Joel; apply them to Chefalitas).
6. 🟢 607/606/608 reports from Odoo 20 (`l10n_do_accounting_report`).

### B. Data migration 18 → 20 (🔴 decision needed)
Odoo provides no free upgrade path for Community 18 → 20, and OpenUpgrade does not support 20 yet. Options:
- **Option 1 (recommended for Nov 1): new Odoo 20 + master data.** Import partners/customers, products, recipes/BoM, taxes, price lists, POS configuration, users, chart of accounts and **opening balances as of Oct 31**. History stays in Odoo 18, read-only, for lookups. Fast and controlled.
- Option 2: full migration with history through Odoo's paid upgrade service (requires an Enterprise subscription; it conflicts with the "own modules, no Enterprise" policy and has uncertain timelines).
- Option 3: OpenUpgrade 18→19→20: not viable before Nov 1.
- 🔴 **Fresh backup of production** at cutover (the certified one is from Oct 5).

### C. Modules (Odoo 20 test on the ThinkCentre)
Already installed in Odoo 20: `l10n_do`, `l10n_do_accounting`, `l10n_do_accounting_report`, `pos_system`, `pos_l10n_do_restaurant`, `point_of_sale` + restaurant/loyalty/self-order, `purchase`, `sale_management`.
Missing in Odoo 20 and used in production (Odoo 18/19):
- 🔴 `stock` (inventory) and its dependencies.
- 🟠 Own modules **not yet installed/tested on 20**: `pos_printing_suite`, `pos_kitchen_core`, `orca_bridge`, `chefalitas_recipe_margin` (needs `mrp`), `chefalitas_purchase_intake` (needs `purchase_stock` + `getupsoft_whatsapp`), `getupsoft_whatsapp`.
- 🟠 Standard modules used in production that need validating on 20: `mrp`, `hr`/`pos_hr` (cashier PINs), `pos_mrp`, `pos_discount`, `pos_sms`, `website`, `pos_event*`, and `pos_any_printer` / `pos_self_order_any_printer` (check whether they exist in 20 or are replaced by `pos_printing_suite`).

### D. Hardware and point of sale (🔴 if POS is used)
- 🔴 Kitchen and receipt printers with `pos_printing_suite` on Odoo 20, **tested on site**.
- 🟠 Kitchen display (`pos_kitchen_core`), cash drawer, scale if any.
- 🟠 Where Odoo 20 runs in production: **at the office** (DESKTOP-3RD2JRI, near the printers, but its tunnel is down today) or **in Miami/ThinkCentre** (the printers would need a local bridge). Needs a decision.

### E. Infrastructure and access
- 🔴 Restore the `chefalitas-prod-wsl2` tunnel (or move production) and the `chefalitas.com.do` domain.
- 🟠 Odoo 20 domain for UAT (`odoo20.chefalitas.com.do` → ThinkCentre tunnel): **waiting on your authorization** for the DNS change.
- 🟠 Automatic Odoo 20 backups (DB + filestore) and a tested restore.

### F. People and cutover
- 🟠 Users (10 active in production), roles, POS PINs, and short training for cashiers and accounting.
- 🔴 Cutover plan: Oct 31 close in Odoo 18 → final backup → load into Odoo 20 → test invoice in production → Nov 1 operation. Rollback: go back to Odoo 18 issuing B01/B02 (paper NCF), if they still have them authorized.

## 3. Proposed timeline (to adjust)
| Dates | What |
|---|---|
| Oct 13–16 | Decide options B and D. Submit the OFV request (A1–A2). Install/test the missing modules on Odoo 20 (C). |
| Oct 17–23 | Master data import on Odoo 20 UAT. Odoo 20 ↔ EasyCount (test environment). Printers on site. |
| Oct 24–29 | UAT with the users. EasyCount production (A3–A4) as soon as the DGII authorizes. Training. |
| Oct 30–31 | Final backup, opening balances, cutover. |
| Nov 1 | Production on Odoo 20 + e-CF. |

## 4. Decisions/data needed from the user
1. Chefalitas's OFV password (or have them submit the "Emisor Electrónico" request in the OFV).
2. Migration option: **new Odoo 20 + master data** (recommended) or full history.
3. Where Odoo 20 production runs (office vs. Miami).
4. Whether Chefalitas still sells through Odoo POS (last sale 2026-04-06).
5. Authorization for the Odoo 20 UAT domain in Cloudflare.
