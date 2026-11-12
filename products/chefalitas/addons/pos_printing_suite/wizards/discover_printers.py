# -*- coding: utf-8 -*-
import ipaddress
import socket
from concurrent.futures import ThreadPoolExecutor

from odoo import fields, models
from odoo.exceptions import UserError

RAW_PORT = 9100  # raw ESC/POS port used by network receipt printers
MAX_HOSTS = 1024


def probe(ip, port=RAW_PORT, timeout=0.4):
    """True when something accepts a TCP connection on the printer port."""
    try:
        with socket.create_connection((str(ip), port), timeout=timeout):
            return True
    except OSError:
        return False


def local_network():
    """Best guess of the server's own /24 (editable in the wizard)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("10.255.255.255", 1))
        ip = sock.getsockname()[0]
    except OSError:
        ip = "192.168.1.1"
    finally:
        sock.close()
    return str(ipaddress.ip_network(f"{ip}/24", strict=False))


def scan(network, prober=probe):
    """Printers answering on the raw port inside a private network (at most MAX_HOSTS addresses)."""
    try:
        net = ipaddress.ip_network((network or "").strip(), strict=False)
    except ValueError:
        raise UserError("Red inválida. Use el formato 192.168.1.0/24.") from None
    if not net.is_private:
        raise UserError("Solo se buscan redes privadas (192.168.x.x, 10.x.x.x, 172.16-31.x.x).")
    hosts = list(net.hosts())
    if len(hosts) > MAX_HOSTS:
        raise UserError("La red es demasiado grande; use una máscara /22 o menor.")
    with ThreadPoolExecutor(max_workers=64) as pool:
        found = list(pool.map(lambda ip: (ip, prober(ip)), hosts))
    return [str(ip) for ip, ok in found if ok]


class PosPrintingDiscoverWizard(models.TransientModel):
    _name = "pos.printing.discover.wizard"
    _description = "Buscar impresoras en la red local"

    config_id = fields.Many2one("pos.config", string="Punto de venta", required=True)
    network = fields.Char("Red a buscar", required=True, default=lambda self: local_network(),
                          help="Red local del cliente en formato CIDR. Si Odoo está en la nube, use el gateway/túnel del agente local.")
    use_type = fields.Selection([("receipt", "Recibos (caja)"), ("preparation", "Preparación (cocina)")],
                                string="Usar como", required=True, default="receipt")
    line_ids = fields.One2many("pos.printing.discover.line", "wizard_id", string="Impresoras encontradas")

    def _reopen(self):
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id,
                "view_mode": "form", "target": "new"}

    def action_scan(self):
        self.ensure_one()
        known = set(self.env["pos.printer"].search([("hw_proxy_ip", "!=", False)]).mapped("hw_proxy_ip"))
        self.line_ids.unlink()
        self.env["pos.printing.discover.line"].create([
            {"wizard_id": self.id, "ip": ip, "name": f"Impresora {ip}", "selected": ip not in known, "known": ip in known}
            for ip in scan(self.network)])
        return self._reopen()

    def action_create(self):
        self.ensure_one()
        chosen = self.line_ids.filtered("selected")
        if not chosen:
            raise UserError("Marque al menos una impresora.")
        field = "receipt_printer_ids" if self.use_type == "receipt" else "preparation_printer_ids"
        for line in chosen:
            printer = self.env["pos.printer"].search([("hw_proxy_ip", "=", line.ip)], limit=1) or self.env["pos.printer"].create({
                "name": line.name, "printer_type": "hw_proxy_any_printer", "hw_proxy_ip": line.ip,
                "use_type": self.use_type})
            self.config_id.write({field: [(4, printer.id)]})
        return {"type": "ir.actions.act_window_close"}


class PosPrintingDiscoverLine(models.TransientModel):
    _name = "pos.printing.discover.line"
    _description = "Impresora encontrada en la red"

    wizard_id = fields.Many2one("pos.printing.discover.wizard", required=True, ondelete="cascade")
    ip = fields.Char(required=True, readonly=True)
    name = fields.Char("Nombre", required=True)
    selected = fields.Boolean("Agregar", default=True)
    known = fields.Boolean("Ya registrada", readonly=True)
