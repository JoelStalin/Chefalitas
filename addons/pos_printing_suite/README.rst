POS Printing Suite (Odoo 18+)
=============================

Unified addon for POS printing via:

- **Local Agent (Windows)** over HTTP
- **HW Proxy / Any Printer**

Configuration lives **only in ``pos.config``**.

Features
--------

- **Local Agent (Windows)**: POS sends a **receipt image** to a local HTTP agent.
- **HW Proxy**: POS sends a **receipt image** to ``/hw_proxy/default_printer_action``.
- **Simple configuration**: only printer names + host/port per POS.

Installation
------------

1. Install the addon (depends on ``point_of_sale``).
2. In each POS configuration, set:

   - **Printing mode**: Local Agent or HW Proxy
   - **Printer (Cashier)** and **Printer (Kitchen)**
   - **Local Agent Host/Port** or **HW Proxy Host/Port**

3. Run the Local Agent on the Windows PC if using Local Agent.

Local Agent (Windows)
---------------------

- **Source**: ``addons/pos_printing_suite/agent_src/local_printer_agent/``
- **Endpoints**:

  - ``GET /health``
  - ``GET /printers``
  - ``POST /print`` (body: ``type`` raw|pdf|image, ``printer``, ``data`` base64)

- **Config**: ``ProgramData\PosPrintingSuite\LocalPrinterAgent\config.json``

  - ``host``, ``port``, ``log_dir``
  - ``token`` is **optional**; if set in the agent config, requests must include
    ``Authorization: Bearer <token>``.

- **Service**: run via ``python win_service.py install`` (pywin32) or NSSM.

Notes
-----

- The addon converts the POS receipt to an **image** before sending it to the agent/proxy.
- If no printer name is configured, the addon does **not** override standard Odoo printing.

Windows Agent (MVP)
-------------------

This module can generate a **ZIP installer** (bundle) for a Windows agent.

Flow
~~~~

1. Open POS Config and go to the **Windows Agent** section.
2. Click **Crear instalable del agente** to generate a ZIP.
3. Click **Descargar e instalar agente** to open instructions and download.
4. Extract the ZIP on the Windows POS machine.
5. Run ``install.ps1`` as Administrator.

Important
~~~~~~~~~

- If no compiled agent is included, build it using the scripts in ``installer/``.
- Recommended build options:

  - **Python + PyInstaller** (simple)
  - **.NET Worker Service** (robust)

The agent should:

- read ``config.json`` (server URL + token),
- send periodic pings to ``/pos_printing_suite/agent/ping``,
- optionally expose a local endpoint for printing.

Server-side build (optional)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you want Odoo to attempt a build on the server when clicking
"Crear instalable del agente", set an environment variable:

``POS_PRINTING_SUITE_AGENT_BUILD_CMD="pyinstaller pyinstaller.spec"``

The build command will run inside ``agent_src/local_printer_agent/installer``.
