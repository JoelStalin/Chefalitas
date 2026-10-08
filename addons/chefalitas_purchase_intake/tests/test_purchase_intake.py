import base64
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

INTAKE = "odoo.addons.chefalitas_purchase_intake.models.purchase_intake.PurchaseIntake"
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")

READING = {
    "reader": "ocr+local", "confidence": 0.93,
    "vendor": {"vat": "101010101", "name": "Distribuidora Avícola"},
    "ncf": "B0100000042", "date": "2026-10-08", "amount_tax": 360.0, "amount_total": 2360.0,
    "lines": [
        {"description": "Pechuga de pollo lb", "quantity": 10, "price_unit": 150.0, "tax_rate": 18},
        {"description": "Aceite galón", "quantity": 2, "price_unit": 250.0, "tax_rate": 18},
    ],
}


@tagged("post_install", "-at_install")
class TestPurchaseIntake(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env["res.partner"].create({"name": "Karla Caja", "purchase_intake_allowed": True})
        cls.stranger = cls.env["res.partner"].create({"name": "Desconocido"})
        cls.channel = cls.env["discuss.channel"].create({"name": "WA Karla", "channel_type": "channel"})
        cls.chicken = cls.env["product.product"].create({
            "name": "Pechuga de pollo lb", "type": "consu", "is_storable": True, "purchase_ok": True})

    def setUp(self):
        super().setUp()
        self.replies = []
        reply = patch(INTAKE + "._reply", lambda intake, text: self.replies.append(text))
        reply.start()
        self.addCleanup(reply.stop)

    def _message(self, author, body="", image=False):
        attachments = []
        if image:
            attachments = [self.env["ir.attachment"].create({"name": "factura.png", "raw": PNG, "mimetype": "image/png"}).id]
        return self.env["mail.message"].create({
            "model": "discuss.channel", "res_id": self.channel.id, "author_id": author.id, "body": body,
            "message_type": "comment", "attachment_ids": [(6, 0, attachments)]})

    def _receive_photo(self, reading=READING):
        with patch(INTAKE + "._orca_extract", return_value=reading) as extract:
            intake = self.env["purchase.intake"]._on_whatsapp_message(self.channel, self._message(self.employee, image=True))
        return intake, extract

    def _say(self, text):
        return self.env["purchase.intake"]._on_whatsapp_message(self.channel, self._message(self.employee, body=text))

    def test_unauthorized_sender_is_ignored(self):
        with patch(INTAKE + "._orca_extract") as extract:
            result = self.env["purchase.intake"]._on_whatsapp_message(self.channel, self._message(self.stranger, image=True))
        self.assertFalse(result)
        extract.assert_not_called()
        self.assertFalse(self.replies)

    def test_photo_is_read_and_summary_sent_for_confirmation(self):
        intake, extract = self._receive_photo()
        self.assertEqual(intake.state, "awaiting_confirmation")
        self.assertEqual(extract.call_args.args[1], "image/png")
        self.assertEqual(base64.b64decode(extract.call_args.args[0]), PNG)
        self.assertEqual((intake.ncf, intake.vendor_vat, intake.amount_total), ("B0100000042", "101010101", 2360.0))
        self.assertEqual(intake.line_ids[0].product_id, self.chicken)  # known product matched by name
        self.assertFalse(intake.line_ids[1].product_id)                # new one, created on confirmation
        self.assertIn("B0100000042", self.replies[-1])
        self.assertIn("Responda SI", self.replies[-1])

    def test_corrections_update_lines(self):
        intake, _ = self._receive_photo()
        self._say("linea 2 cantidad 3")
        self._say("Línea 1 precio 155.50")
        self.assertEqual(intake.line_ids[1].quantity, 3)
        self.assertEqual(intake.line_ids[0].price_unit, 155.5)
        self._say("linea 9 cantidad 1")
        self.assertIn("No existe la línea 9", self.replies[-1])
        self._say("linea 1 cantidad muchas")
        self.assertIn("no es un número", self.replies[-1])
        self._say("hola")
        self.assertIn("No entendí", self.replies[-1])
        self.assertEqual(intake.state, "awaiting_confirmation")

    def test_confirmation_creates_order_receipt_and_bill_with_photo(self):
        intake, _ = self._receive_photo()
        self._say("SI")
        self.assertEqual(intake.state, "done")
        order, bill = intake.purchase_id, intake.bill_id
        self.assertEqual(order.state, "purchase")
        self.assertEqual(order.partner_id.vat, "101010101")
        self.assertEqual(self.chicken.qty_available, 10)  # stock received
        oil = intake.line_ids[1].product_id
        self.assertTrue(oil.is_storable)
        self.assertEqual(oil.qty_available, 2)
        self.assertEqual((bill.move_type, bill.state, bill.ref), ("in_invoice", "draft", "B0100000042"))
        self.assertEqual(bill.amount_untaxed, 2000.0)
        self.assertTrue(self.env["ir.attachment"].search_count([("res_model", "=", "account.move"), ("res_id", "=", bill.id)]))
        self.assertTrue(self.env["ir.attachment"].search_count([("res_model", "=", "purchase.order"), ("res_id", "=", order.id)]))
        self.assertIn(order.name, self.replies[-1])

    def test_vendor_names_are_learned_for_next_invoice(self):
        intake, _ = self._receive_photo()
        self._say("linea 2 producto Pechuga")  # employee maps the second line to an existing product
        self.assertEqual(intake.line_ids[1].product_id, self.chicken)
        self._say("SI")
        reading = dict(READING, ncf="B0100000043",
                       lines=[{"description": "Aceite galón", "quantity": 1, "price_unit": 250.0, "tax_rate": 18}])
        second, _ = self._receive_photo(reading)
        self.assertEqual(second.line_ids.product_id, self.chicken)  # learned from the confirmation

    def test_no_discards(self):
        intake, _ = self._receive_photo()
        self._say("no")
        self.assertEqual(intake.state, "rejected")
        self.assertFalse(intake.purchase_id)

    def test_orca_failure_is_reported_and_creates_nothing(self):
        with patch(INTAKE + "._orca_extract", side_effect=ConnectionError("ORCA down")):
            intake = self.env["purchase.intake"]._on_whatsapp_message(self.channel, self._message(self.employee, image=True))
        self.assertEqual(intake.state, "error")
        self.assertIn("ORCA down", intake.error)
        self.assertIn("No pude leer", self.replies[-1])
        self.assertFalse(intake.purchase_id)
