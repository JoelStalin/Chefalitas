from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPrintingSuitePrinters(TransactionCase):

    def test_local_agent_settings_create_odoo20_printers(self):
        config = self.env["pos.config"].create({
            "name": "Caja 1", "printing_mode": "local_agent",
            "local_printer_cashier_name": "EPSON-CAJA", "local_printer_kitchen_name": "EPSON-COCINA",
        })
        receipt = config.receipt_printer_ids.filtered(lambda p: p.printer_type == "local_agent")
        kitchen = config.preparation_printer_ids.filtered(lambda p: p.printer_type == "local_agent")
        self.assertEqual(receipt.local_printer_name, "EPSON-CAJA")
        self.assertEqual(kitchen.local_printer_name, "EPSON-COCINA")
        self.assertEqual(kitchen.use_type, "preparation")

        config.write({"local_printer_cashier_name": "EPSON-NUEVA"})
        self.assertEqual(config.receipt_printer_ids.filtered(lambda p: p.printer_type == "local_agent").local_printer_name,
                         "EPSON-NUEVA")

        config.write({"printing_mode": "odoo_default"})
        self.assertFalse((config.receipt_printer_ids | config.preparation_printer_ids)
                         .filtered(lambda p: p.printer_type == "local_agent"))
