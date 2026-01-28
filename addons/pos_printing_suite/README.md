# POS Printing Suite (Odoo 18+)

Unified addon for POS printing: **Local Agent** (Windows service, token per device) and **HW Proxy / Any Printer**.

**Server vs agent**: Odoo runs on **Ubuntu** (or your Linux server). The addon has no extra Python dependencies on the server; the repo `addons/requirements.txt` is used by the Odoo container. The **Local Printer Agent** is built and run on **Windows** only; its Python deps are in `agent_src/local_printer_agent/requirements-windows.txt` (do not install those on Ubuntu).

## Features

- **Local Agent (Windows)**: Browser POS sends print jobs to `http://127.0.0.1:9060` with a Bearer token. One token per **POS Print Device**; install the agent on each PC as a Windows service (pywin32 or NSSM).
- **HW Proxy**: Use an existing hw_proxy/any-printer IP for receipts/kitchen.
- **Token per device**: Each device record in Odoo has a unique token; the installer (built on Windows) embeds the token in `ProgramData` config.
- **No IP/port in Odoo**: Agent address is fixed at `127.0.0.1:9060`.

## Installation

1. Install the addon in Odoo (Point of Sale and Mail required).
2. **POS config**: In each Point of Sale form, set **Printing mode** (Local Agent or HW Proxy), attach a **Local Agent Device** if using Local Agent, and set printer names (cashier/kitchen).
3. **Devices**: Create a **POS Print Device** per PC (Configuration → POS Print Devices). Activate it; use **Upload installer** to attach the Windows installer built for that device (token must be in the build).
4. **Agent build** (on Windows only): `pip install -r agent_src/local_printer_agent/requirements-windows.txt` then run `installer/build.bat` or `installer/build.ps1` to build the agent (PyInstaller onedir). Optionally use Inno Setup to produce `LocalPrinterAgent-Setup.exe`. When building for a specific device, inject that device’s token into the config (e.g. `config.json` in `ProgramData`).

## Agent (Windows)

- **Source**: `addons/pos_printing_suite/agent_src/local_printer_agent/`.
- **Endpoints**: `GET /health`, `GET /printers` (auth), `POST /print` (auth; body: `type` raw|pdf|image, `printer`, `data` base64).
- **Config**: `ProgramData\PosPrintingSuite\LocalPrinterAgent\config.json` with `token`, `host`, `port`, `log_dir`.
- **Service**: Run as Windows service via `python win_service.py install` (pywin32) or NSSM. Use **onedir** build (not onefile) for services.
- **Logs**: `…\LocalPrinterAgent\logs\agent.log`.

## Security

- **Revoke**: Use **Revoke** on a POS Print Device to invalidate its token (no new prints; re-activate or create a new device for a new token).
- **Download**: Only users with POS Manager group can download the installer via `/pos_printing_suite/agent/download/<device_id>`.

## Self-Order

If you use **pos_self_order**, you can extend its printer service to use the same Local Agent / HW Proxy drivers (same token and config). The addon does not depend on `pos_self_order`; implement the Self-Order printer patch in a separate bridge module if needed.

## Migration from older modules

1. Uninstall (in order): `pos_self_order_any_printer_local`, `pos_self_order_any_printer`, `pos_client_printer`, `pos_any_printer_local`, `pos_any_printer`.
2. Install **pos_printing_suite**.
3. Create POS Print Devices, assign them to the POS configs, and upload/download the installer per device.

## Checklist (Odoo 18 / Windows)

- Assets declared in `__manifest__.py` under `point_of_sale._assets_pos`.
- No `attrs` in views; use `invisible` / help where needed.
- Token unique per device; agent validates Bearer token.
- Agent: onedir, service, no GUI, fixed config/log paths.
- Installer download from Odoo serves pre-built file (no compilation on server).
- `sudo()` only where necessary (e.g. attachment read for download).
