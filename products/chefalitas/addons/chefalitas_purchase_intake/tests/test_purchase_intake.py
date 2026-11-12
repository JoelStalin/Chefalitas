import base64
from itertools import count
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

INTAKE = "odoo.addons.chefalitas_purchase_intake.models.purchase_intake.PurchaseIntake"
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
SEQ = count(1)

READING = {
    "reader": "ocr+rules", "confidence": 1.0,
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
        cls.account = cls.env["gs.whatsapp.account"].create({
            "name": "Compras", "phone_number_id": "1", "token": "t", "app_secret": "s", "verify_token": "v"})
        cls.employee = cls.env["res.partner"].create({"name": "Karla Caja", "purchase_intake_allowed": True})
        cls.stranger = cls.env["res.partner"].create({"name": "Desconocido"})
        Conv = cls.env["gs.whatsapp.conversation"]
        cls.conv = Conv.create({"account_id": cls.account.id, "wa_number": "18095550101", "partner_id": cls.employee.id})
        cls.other = Conv.create({"account_id": cls.account.id, "wa_number": "18095550199", "partner_id": cls.stranger.id})
        cls.chicken = cls.env["product.product"].create({
            "name": "Pechuga de pollo lb", "type": "consu", "is_storable": True, "purchase_ok": True})

    def setUp(self):
        super().setUp()
        self.replies = []
        for target, value in ((INTAKE + "._reply", lambda intake, text: self.replies.append(text)),
                              (INTAKE + "._orca_available", lambda intake: True)):
            p = patch(target, value)
            p.start()
            self.addCleanup(p.stop)

    def _photo(self, conv=None, reading=READING):
        with patch(INTAKE + "._orca_extract", return_value=reading) as extract:
            (conv or self.conv)._receive(f"wamid.P{next(SEQ)}", "image", media=("factura.png", PNG, "image/png"))
        return self.env["purchase.intake"].search([], limit=1, order="id desc"), extract

    def _say(self, text):
        self.conv._receive(f"wamid.T{next(SEQ)}", "text", text=text)

    def test_unauthorized_sender_is_ignored(self):
        with patch(INTAKE + "._orca_extract") as extract:
            self.other._receive("wamid.X", "image", media=("f.png", PNG, "image/png"))
        extract.assert_not_called()
        self.assertFalse(self.env["purchase.intake"].search_count([("sender_id", "=", self.stranger.id)]))

    def test_photo_is_read_and_summary_sent_for_confirmation(self):
        intake, extract = self._photo()
        self.assertEqual(intake.state, "awaiting_confirmation")
        self.assertEqual(base64.b64decode(extract.call_args.args[0]), PNG)
        self.assertEqual((intake.ncf, intake.vendor_vat, intake.amount_total), ("B0100000042", "101010101", 2360.0))
        self.assertEqual(intake.line_ids[0].product_id, self.chicken)
        self.assertFalse(intake.line_ids[1].product_id)
        self.assertIn("Responda SI", self.replies[-1])

    def test_corrections_update_lines(self):
        intake, _ = self._photo()
        self._say("linea 2 cantidad 3")
        self._say("Línea 1 precio 155.50")
        self.assertEqual((intake.line_ids[1].quantity, intake.line_ids[0].price_unit), (3, 155.5))
        self._say("linea 9 cantidad 1")
        self.assertIn("No existe la línea 9", self.replies[-1])
        self._say("hola")
        self.assertIn("No entendí", self.replies[-1])

    def test_confirmation_creates_order_receipt_and_bill_with_photo(self):
        intake, _ = self._photo()
        self._say("SI")
        self.assertEqual(intake.state, "done")
        order, bill = intake.purchase_id, intake.bill_id
        self.assertEqual(order.state, "purchase")
        self.assertEqual(self.chicken.qty_available, 10)
        self.assertEqual(intake.line_ids[1].product_id.qty_available, 2)
        self.assertEqual((bill.move_type, bill.state, bill.ref, bill.amount_untaxed), ("in_invoice", "draft", "B0100000042", 2000.0))
        self.assertTrue(self.env["ir.attachment"].search_count([("res_model", "=", "account.move"), ("res_id", "=", bill.id)]))

    def test_vendor_names_are_learned_for_next_invoice(self):
        intake, _ = self._photo()
        self._say("linea 2 producto Pechuga")
        self._say("SI")
        reading = dict(READING, ncf="B0100000043",
                       lines=[{"description": "Aceite galón", "quantity": 1, "price_unit": 250.0, "tax_rate": 18}])
        second, _ = self._photo(reading=reading)
        self.assertEqual(second.line_ids.product_id, self.chicken)

    def test_no_discards(self):
        intake, _ = self._photo()
        self._say("no")
        self.assertEqual(intake.state, "rejected")

    def test_without_orca_a_person_registers_it_in_odoo(self):
        with patch(INTAKE + "._orca_available", lambda intake: False), patch(INTAKE + "._orca_extract") as extract:
            self.conv._receive("wamid.M1", "image", media=("factura.png", PNG, "image/png"))
        extract.assert_not_called()
        intake = self.env["purchase.intake"].search([], limit=1, order="id desc")
        self.assertEqual(intake.state, "manual")
        self.assertIn("encargado", self.replies[-1])
        intake.write({"vendor_vat": "101010101", "ncf": "B0100000050", "line_ids": [
            (0, 0, {"sequence": 1, "description": "Pechuga de pollo lb", "quantity": 4, "price_unit": 150.0})]})
        intake.action_register()
        self.assertEqual(intake.state, "done")
        self.assertEqual(self.chicken.qty_available, 4)
        self.assertEqual(intake.bill_id.ref, "B0100000050")

    def test_orca_failure_falls_back_to_manual(self):
        with patch(INTAKE + "._orca_extract", side_effect=ConnectionError("ORCA down")):
            self.conv._receive("wamid.F1", "image", media=("factura.png", PNG, "image/png"))
        intake = self.env["purchase.intake"].search([], limit=1, order="id desc")
        self.assertEqual(intake.state, "manual")
        self.assertIn("ORCA down", intake.error)
        self.assertFalse(intake.purchase_id)
