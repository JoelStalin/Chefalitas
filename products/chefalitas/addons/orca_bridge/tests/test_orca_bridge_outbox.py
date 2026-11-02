import time
from datetime import timedelta
from unittest.mock import patch

import requests

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged

CLIENT = "odoo.addons.orca_bridge.models.orca_bridge_client.requests"
ORCA = "https://orca.test"


def _ok(*args, **kwargs):
    r = requests.Response()
    r.status_code = 202
    return r


@tagged("post_install", "-at_install")
class TestOrcaBridgeOutbox(TransactionCase):

    def setUp(self):
        super().setUp()
        params = self.env["ir.config_parameter"].sudo()
        params.set_str("orca_bridge.url", ORCA)
        params.set_str("orca_bridge.connection_id", "chefalitas-test")
        params.set_str("orca_bridge.access_token", "orca_at_ok")  # valid token: no OAuth call in these tests
        params.set_int("orca_bridge.token_expires_at", int(time.time()) + 3600)
        self.outbox = self.env["orca.bridge.outbox"]
        self.outbox.sudo().search([]).unlink()  # rows left by other test classes would be sent too

    def _events(self, n):
        return [{"connection": "chefalitas-test", "model": "account.move", "event": "post", "ids": [i], "fields": ["state"]}
                for i in range(1, n + 1)]

    def test_events_are_delivered_in_order_and_marked_sent(self):
        rows = self.outbox._enqueue(self._events(3))
        with patch(CLIENT + ".post", side_effect=_ok) as post:
            self.assertEqual(self.outbox._send_pending(), 3)
        self.assertEqual([c.kwargs["json"]["ids"] for c in post.call_args_list], [[1], [2], [3]])
        self.assertEqual(set(rows.mapped("state")), {"sent"})
        self.assertEqual(post.call_args.kwargs["headers"], {"Authorization": "Bearer orca_at_ok"})

    def test_orca_down_keeps_events_and_stops_at_first_failure(self):
        rows = self.outbox._enqueue(self._events(3))
        calls = iter([_ok(), requests.ConnectionError("down")])

        def flaky(*a, **k):
            r = next(calls)
            if isinstance(r, Exception):
                raise r
            return r
        with patch(CLIENT + ".post", side_effect=flaky) as post:
            self.assertEqual(self.outbox._send_pending(), 1)
        self.assertEqual(post.call_count, 2)  # the third event is not tried after the failure: order is kept
        self.assertEqual(rows.mapped("state"), ["sent", "pending", "pending"])
        self.assertEqual(rows[1].attempts, 1)
        self.assertIn("down", rows[1].last_error)
        with patch(CLIENT + ".post", side_effect=_ok):
            self.assertEqual(self.outbox._send_pending(), 2)  # next run delivers what was kept
        self.assertEqual(set(rows.mapped("state")), {"sent"})

    def test_refused_event_is_kept(self):
        rows = self.outbox._enqueue(self._events(1))
        refused = requests.Response()
        refused.status_code = 503
        with patch(CLIENT + ".post", return_value=refused):
            self.assertEqual(self.outbox._send_pending(), 0)
        self.assertEqual(rows.state, "pending")
        self.assertEqual(rows.last_error, "HTTP 503")

    def test_nothing_is_sent_when_not_connected(self):
        self.env["ir.config_parameter"].sudo().set_str("orca_bridge.connection_id", "")
        rows = self.outbox._enqueue(self._events(1))
        with patch(CLIENT + ".post") as post:
            self.assertEqual(self.outbox._send_pending(), 0)
        post.assert_not_called()
        self.assertEqual(rows.state, "pending")

    def test_payload_has_no_values(self):
        partner = self.env["res.partner"].create({"name": "X", "email": "secreto@example.test"})
        events = self.env["orca.bridge.client"]._events_payload(
            "c", {("res.partner", "write"): {"ids": {partner.id}, "fields": {"email"}}})
        rows = self.outbox._enqueue(events)
        self.assertNotIn("secreto@example.test", str(rows.payload))

    def test_cron_purges_old_sent_events_only(self):
        old, recent, pending = self.outbox._enqueue(self._events(3))
        old.write({"state": "sent", "sent_at": fields.Datetime.now() - timedelta(days=8)})
        recent.write({"state": "sent", "sent_at": fields.Datetime.now()})
        self.env["ir.config_parameter"].sudo().set_str("orca_bridge.connection_id", "")  # cron cannot send now
        self.outbox._cron_send()
        self.assertFalse(old.exists())
        self.assertTrue(recent.exists() and pending.exists())

    def test_cron_record_exists(self):
        cron = self.env.ref("orca_bridge.cron_orca_bridge_outbox")
        self.assertEqual(cron.code.strip(), "model._cron_send()")


@tagged("post_install", "-at_install")
class TestOrcaServerActionCodeGuard(TransactionCase):

    def setUp(self):
        super().setUp()
        self.admin = new_test_user(self.env, login="plain_admin", groups="base.group_system")
        self.model = self.env.ref("base.model_res_partner")

    def test_plain_admin_cannot_write_python_code(self):
        actions = self.env["ir.actions.server"].with_user(self.admin)
        with self.assertRaises(AccessError):
            actions.create({"name": "x", "model_id": self.model.id, "state": "code", "code": "pass"})
        action = self.env["ir.actions.server"].create({"name": "y", "model_id": self.model.id, "state": "code", "code": "pass"})
        with self.assertRaises(AccessError):
            action.with_user(self.admin).write({"code": "env['res.partner'].search([]).unlink()"})

    def test_plain_admin_can_still_manage_non_code_actions(self):
        action = self.env["ir.actions.server"].with_user(self.admin).create(
            {"name": "z", "model_id": self.model.id, "state": "object_write", "update_path": "name", "value": "v"})
        action.write({"name": "renamed"})
        self.assertEqual(action.name, "renamed")

    def test_dev_admin_group_can_write_code(self):
        self.admin.group_ids |= self.env.ref("orca_bridge.group_orca_dev_admin")
        action = self.env["ir.actions.server"].with_user(self.admin).create(
            {"name": "ok", "model_id": self.model.id, "state": "code", "code": "pass"})
        self.assertEqual(action.code, "pass")

    def test_owner_admin_and_orca_user_are_dev_admins(self):
        group = self.env.ref("orca_bridge.group_orca_dev_admin")
        self.assertIn(self.env.ref("base.user_admin"), group.user_ids)
        self.assertIn(self.env.ref("orca_bridge.user_orca_bridge"), group.user_ids)
