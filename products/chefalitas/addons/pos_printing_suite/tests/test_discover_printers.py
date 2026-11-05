from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.pos_printing_suite.wizards.discover_printers import scan


@tagged("post_install", "-at_install")
class TestDiscoverPrinters(TransactionCase):

    def test_scan_returns_only_hosts_that_answer(self):
        self.assertEqual(scan("192.168.1.0/29", prober=lambda ip: str(ip) in ("192.168.1.2", "192.168.1.5")),
                         ["192.168.1.2", "192.168.1.5"])

    def test_scan_refuses_public_and_huge_networks(self):
        for bad in ("8.8.8.0/24", "10.0.0.0/16", "no-es-una-red"):
            with self.assertRaises(UserError):
                scan(bad, prober=lambda ip: True)

    def test_wizard_creates_printers_for_the_point_of_sale(self):
        config = self.env["pos.config"].create({"name": "Caja DISC"})
        wizard = self.env["pos.printing.discover.wizard"].create({"config_id": config.id, "network": "192.168.1.0/29"})
        self.env["pos.printing.discover.line"].create({"wizard_id": wizard.id, "ip": "192.168.1.9", "name": "Cocina"})
        wizard.action_create()
        printer = config.receipt_printer_ids
        self.assertEqual(printer.hw_proxy_ip, "192.168.1.9")
        self.assertEqual(printer.printer_type, "hw_proxy_any_printer")
        wizard.action_create()  # a second run reuses the same printer
        self.assertEqual(self.env["pos.printer"].search_count([("hw_proxy_ip", "=", "192.168.1.9")]), 1)
