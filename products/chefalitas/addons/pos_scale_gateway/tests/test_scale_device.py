import uuid

from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase


class TestScaleDevice(TransactionCase):
    def setUp(self):
        super().setUp()
        self.device = self.env["pos.scale.device"].create({"name": "QA Scale"})

    def _pair(self):
        notice = self.device.action_pair()
        code = notice["params"]["message"].split(": ")[1].split(" ")[0]
        return self.device.exchange_pairing_code(code)

    def test_pairing_one_time_and_revocation(self):
        token = self._pair()
        self.assertTrue(token)
        self.assertFalse(self.device.pairing_hash)
        self.device.action_revoke()
        with self.assertRaises(AccessError):
            self.device.accept_reading(token, {
                "sample_id": str(uuid.uuid4()), "weight": 1, "unit": "lb",
            })

    def test_valid_reading_and_duplicate_rejected(self):
        token = self._pair()
        payload = {"sample_id": str(uuid.uuid4()), "weight": 1.25, "unit": "lb"}
        reading = self.device.accept_reading(token, payload)
        self.assertEqual(reading.weight, 1.25)
        with self.assertRaises(ValidationError):
            self.device.accept_reading(token, payload)

    def test_unstable_or_invalid_weight_cannot_enter(self):
        token = self._pair()
        for weight in (0, -1, 100001):
            with self.assertRaises(ValidationError):
                self.device.accept_reading(token, {
                    "sample_id": str(uuid.uuid4()), "weight": weight, "unit": "lb",
                })
