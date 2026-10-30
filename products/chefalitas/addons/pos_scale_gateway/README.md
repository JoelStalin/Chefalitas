# POS Scale Gateway (Odoo 20)

This addon pairs a local scale gateway to a remote Odoo POS. It does not need inbound access to the cashier PC.

## Install and configure

1. Add `integrations/odoo/shared-addons/v20` to the Odoo addon path, update Apps, install **POS Scale Gateway**.
2. In Point of Sale > Scales, create one device per physical scale. Click **Generate pairing code** and copy the one-time 10-minute code.
3. In the POS configuration, choose this scale in **Scale device**.
4. Mark each weighed product **To Weigh**. Optionally enter its **Scale PLU**. The product UoM must be a weight unit.
5. Install the gateway on the cashier PC using the Windows artifact from the `Odoo Scale Gateway portable build` workflow or the Python package source. Edit `config.example.json` with the Odoo HTTPS URL, device ID, serial port or TCP endpoint, and parser expressions.
6. Run `GetUpSoftScaleGateway.exe --config config.json pair --code CODE`, then `GetUpSoftScaleGateway.exe --config config.json run`. Use Task Scheduler to start it on login. Treat config.json as a secret after pairing.
7. Open POS, select a weighed product order line, place the item on the scale, and click **Scale**. The latest stable reading must be under five seconds old. Odoo converts lb or kg to the product UoM and updates the line quantity; POS calculates price and total.

For USB scales, use their virtual COM port (Windows) or `/dev/ttyUSB*` (Linux). Raw USB HID needs its protocol specification and a transport adapter. A TCP scale must expose newline-delimited frames. The MK-A01 parser is intentionally configurable until its manual or sample frames are available.

## Safety and rollback

Pairing issues a random token once and stores only its SHA-256 digest in Odoo. Re-pairing or revoking invalidates the previous token. The gateway enforces HTTPS for remote hosts and accepts only frames matching the stable expression. No scale reading can be consumed twice in POS. Stop the gateway to pause readings. To roll back, revoke the device, clear its POS configuration, and uninstall the addon after open POS sessions are closed. Existing POS orders are not rewritten.

The gateway does not drive the scale's built-in label printer or synchronize its PLU keypad. Those functions require the MK-A01 vendor protocol.
