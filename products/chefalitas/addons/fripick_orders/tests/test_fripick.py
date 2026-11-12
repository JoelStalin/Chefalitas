import base64
import json
from datetime import date, datetime

from odoo.tests import HttpCase, TransactionCase, tagged


@tagged("post_install", "-at_install", "fripick")
class TestFripick(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.fripick_partner = cls.env["res.partner"].create({"name": "Fripick SRL"})
        cls.company.write({"fripick_partner_id": cls.fripick_partner.id, "fripick_invoice_issuer": "company"})
        cls.product = cls.env["product.product"].create({"name": "Mofongo", "list_price": 450})

    def _order(self, name, when, total=100.0):
        return self.env["fripick.order"].create({
            "name": name, "company_id": self.company.id, "closed_at": when, "amount_total": total,
            "line_ids": [(0, 0, {"product_id": self.product.id, "name": "Mofongo", "qty": 2, "preparation": "sin sal"})],
        })

    def test_kitchen_ticket_has_items_preparation_and_cut(self):
        order = self._order("ORD-1", datetime(2026, 9, 10, 12, 0))
        ticket = self.env["pos.order"].browse()._fripick_kitchen_ticket(order)
        self.assertIn(b"COMANDA", ticket)
        self.assertIn(b"2 x Mofongo", ticket)
        self.assertIn(b"sin sal", ticket)
        self.assertTrue(ticket.endswith(b"\x1dV\x00"))

    def test_daily_sync_updates_known_companies_and_never_creates(self):
        self.company.vat = "131880681"
        before = self.env["res.company"].search_count([])
        result = self.env["fripick.sync"].apply([
            {"external_id": "FP-1", "vat": "131880681", "invoice_issuer": "fripick"},
            {"external_id": "FP-404", "vat": "999999999", "name": "Desconocida"},
        ])
        self.assertEqual(result["updated"], 1)
        self.assertEqual(result["unknown"], ["FP-404"])
        self.assertEqual(self.company.fripick_external_id, "FP-1")
        self.assertEqual(self.company.fripick_invoice_issuer, "fripick")
        self.assertEqual(self.env["res.company"].search_count([]), before)

    def test_monthly_invoice_groups_last_month_once(self):
        self._order("ORD-A", datetime(2026, 9, 5, 10, 0), 100)
        self._order("ORD-B", datetime(2026, 9, 28, 20, 0), 250)
        self._order("ORD-C", datetime(2026, 10, 2, 9, 0), 999)  # current month: not invoiced yet
        moves = self.env["fripick.billing"].run(today=date(2026, 10, 1))
        self.assertEqual(len(moves), 1)
        self.assertEqual(moves.partner_id, self.fripick_partner)
        self.assertAlmostEqual(sum(moves.invoice_line_ids.mapped("price_unit")), 350)
        self.assertEqual(len(self.env["fripick.order"].search([("invoice_id", "=", moves.id)])), 2)
        self.assertFalse(self.env["fripick.billing"].run(today=date(2026, 10, 1)), "a second run must not invoice again")

    def test_gateway_jobs_stay_queued_until_pulled(self):
        printer = self.env["pos.printer"].create({"name": "Cocina", "printer_type": "cloud_gateway"})
        self.assertGreaterEqual(len(printer.gateway_token), 20)
        job = self.env["fripick.print.job"].create({"printer_id": printer.id, "kind": "kitchen", "payload": base64.b64encode(b"x").decode()})
        job.dispatch()
        self.assertEqual(job.state, "queued")

    def test_direct_printer_failure_is_retried_then_failed(self):
        printer = self.env["pos.printer"].create({"name": "Caja", "printer_type": "hw_proxy_any_printer",
                                                  "hw_proxy_ip": "127.0.0.1", "network_port": 9})
        job = self.env["fripick.print.job"].create({"printer_id": printer.id, "kind": "label", "payload": base64.b64encode(b"x").decode()})
        for _ in range(5):
            job.dispatch()
        self.assertEqual(job.state, "failed")
        self.assertEqual(job.attempts, 5)


@tagged("post_install", "-at_install", "fripick")
class TestFripickGatewayHttp(HttpCase):
    def test_pull_and_ack_with_token_only(self):
        printer = self.env["pos.printer"].create({"name": "Cocina nube", "printer_type": "cloud_gateway"})
        job = self.env["fripick.print.job"].create({"printer_id": printer.id, "kind": "kitchen", "payload": base64.b64encode(b"hola").decode()})
        self.assertEqual(self.url_open("/fripick/gateway/jobs", headers={"Authorization": "Bearer " + "x" * 30}).status_code, 401)
        resp = self.url_open("/fripick/gateway/jobs", headers={"Authorization": f"Bearer {printer.gateway_token}"})
        self.assertEqual(resp.status_code, 200)
        jobs = resp.json()["jobs"]
        self.assertEqual([j["id"] for j in jobs], [job.id])
        self.assertEqual(base64.b64decode(jobs[0]["data"]), b"hola")
        ack = self.url_open("/fripick/gateway/ack", data=json.dumps({"id": job.id, "ok": True}),
                            headers={"Authorization": f"Bearer {printer.gateway_token}", "Content-Type": "application/json"})
        self.assertTrue(ack.json()["ok"])
        job.invalidate_recordset()
        self.assertEqual(job.state, "done")
