from odoo.tests import tagged
from odoo.addons.point_of_sale.tests.common import TestPoSCommon


@tagged("post_install", "-at_install")
class TestReceiptOrderBarcode(TestPoSCommon):
    def setUp(self):
        super().setUp()
        self.config = self.basic_config
        self.product = self.create_product("Producto de prueba", self.categ_basic, 10.0)

    def _order(self):
        self.open_new_session()
        orders = [self.create_ui_order_data([(self.product, 1)])]
        return self.env["pos.order"].browse(self.env["pos.order"].sync_from_ui(orders)["pos.order"][0]["id"])

    def test_barcode_value_is_the_order_reference(self):
        order = self._order()
        self.assertTrue(order.pos_reference)
        self.assertEqual(order._order_receipt_barcode_value(), order.pos_reference.strip())

    def test_receipt_data_carries_a_barcode_image(self):
        order = self._order()
        data = order.order_receipt_generate_data()
        self.assertTrue(data["image"]["order_barcode"].startswith("data:image/png;base64,"))

    def test_receipt_html_shows_the_barcode(self):
        order = self._order()
        self.assertIn('name="order_barcode"', order.order_receipt_generate_html())
