# POS Printing Suite (Odoo 18+)

Unified addon for POS printing via:
- **Local Agent (Windows)** over HTTP
- **HW Proxy / Any Printer**

Configuration lives **only in `pos.config`**.

## Features

- **Local Agent (Windows)**: POS sends a **receipt image** to a local HTTP agent.
- **HW Proxy**: POS sends a **receipt image** to `/hw_proxy/default_printer_action`.
- **Simple configuration**: only printer names + host/port per POS.

## Installation

1. Install the addon (depends on `point_of_sale`).
2. In each POS configuration, set:
   - **Printing mode**: Local Agent or HW Proxy
   - **Printer (Cashier)** and **Printer (Kitchen)**
   - **Local Agent Host/Port** or **HW Proxy Host/Port**
3. Run the Local Agent on the Windows PC if using Local Agent.

## Local Agent (Windows)

- **Source**: `addons/pos_printing_suite/agent_src/local_printer_agent/`
- **Endpoints**:
  - `GET /health`
  - `GET /printers`
  - `POST /print` (body: `type` raw|pdf|image, `printer`, `data` base64)
- **Config**: `ProgramData\PosPrintingSuite\LocalPrinterAgent\config.json`
  - `host`, `port`, `log_dir`
  - `token` is **optional**; if set in the agent config, requests must include `Authorization: Bearer <token>`.
- **Service**: run via `python win_service.py install` (pywin32) or NSSM.

## Notes

- The addon converts the POS receipt to an **image** before sending it to the agent/proxy.
- If no printer name is configured, the addon does **not** override standard Odoo printing.
