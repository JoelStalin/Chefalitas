"""Pruebas sin Odoo del cliente EasyCount y del constructor de payload (todos los tipos e-CF)."""
import io
import json
import os
import sys
import unittest
import urllib.error
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "models"))

from easycount_client import EasyCountClient, EasyCountError
from easycount_payload import build_issue_payload


class FakeResp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


def opener_factory(status=200, body=None, record=None):
    def opener(req, timeout=None):
        if record is not None:
            record.append((req.method, req.full_url, dict(req.header_items()), req.data))
        if status != 200:
            raise urllib.error.HTTPError(req.full_url, status, "err", {}, io.BytesIO(json.dumps(body or {}).encode()))
        return FakeResp(json.dumps(body or {}).encode())
    return opener


class ClientTests(unittest.TestCase):
    def test_bearer_header_and_paths(self):
        rec = []
        c = EasyCountClient("http://ec.local/", "tok", opener=opener_factory(body={"encf": "E310000000001"}, record=rec))
        self.assertEqual(c.allocate_encf("E31"), "E310000000001")
        method, url, headers, data = rec[0]
        self.assertEqual((method, url), ("POST", "http://ec.local/odoo/v1/encf/allocate"))
        self.assertEqual(headers["Authorization"], "Bearer tok")
        self.assertEqual(json.loads(data), {"eCfType": "E31"})

    def test_http_error_mapped(self):
        c = EasyCountClient("http://ec.local", "tok", opener=opener_factory(401, {"detail": "Token invalido"}))
        with self.assertRaises(EasyCountError) as cm:
            c.health()
        self.assertEqual(cm.exception.status, 401)
        self.assertIn("Token invalido", str(cm.exception))

    def test_connection_error_has_no_status(self):
        def boom(req, timeout=None):
            raise urllib.error.URLError("refused")
        with self.assertRaises(EasyCountError) as cm:
            EasyCountClient("http://x", "t", opener=boom).health()
        self.assertIsNone(cm.exception.status)

    def test_config_validation_and_oauth2_reserved(self):
        for args in (("", "t"), ("http://x", "")):
            with self.assertRaises(EasyCountError):
                EasyCountClient(*args)
        with self.assertRaises(EasyCountError):
            EasyCountClient("http://x", "t", auth_mode="oauth2")


def tax(amount):
    return NS(amount=amount, amount_type="percent")


def move(prefix, taxes=(18.0,), vat="131566332", country="DO", **kw):
    line = NS(display_type="product", name="Plato", product_id=NS(display_name="Plato"), quantity=2.0,
              price_unit=350.0, discount=10.0, tax_ids=[tax(t) for t in taxes])
    cur = NS(name="DOP", _get_conversion_rate=lambda *a: 1.0)
    base = dict(
        id=7, l10n_do_fiscal_number=None, invoice_date="2026-10-05", date="2026-10-05",
        l10n_latam_document_type_id=NS(doc_code_prefix=prefix),
        partner_id=NS(commercial_partner_id=NS(vat=vat, name="Cliente", country_id=NS(code=country))),
        invoice_line_ids=NS(filtered=lambda f: [line]), currency_id=cur, company_id=NS(currency_id=cur),
        amount_total=630.0, l10n_do_origin_ncf=None, l10n_do_ecf_modification_code=None,
        reversed_entry_id=None, debit_origin_id=None,
    )
    base.update(kw)
    return NS(**base)


class PayloadTests(unittest.TestCase):
    def test_every_type_builds(self):
        for prefix in ("E31", "E32", "E41", "E43", "E44", "E45", "E46", "E47"):
            p = build_issue_payload(move(prefix), "E310000000001")
            self.assertEqual(p["eCfType"], prefix)
            self.assertEqual(p["lines"][0]["discount"], 70.0)
            self.assertEqual(p["lines"][0]["itbisRate"], 18.0)
            self.assertEqual(p["totalAmount"], 630.0)

    def test_notes_carry_reference(self):
        orig = NS(invoice_date="2026-10-01")
        for prefix, kw in (("E34", {"reversed_entry_id": orig}), ("E33", {"debit_origin_id": orig})):
            p = build_issue_payload(move(prefix, l10n_do_origin_ncf="E310000000009", **kw))
            self.assertEqual((p["referenceEncf"], p["referenceDate"], p["modificationCode"]),
                             ("E310000000009", "2026-10-01", "3"))

    def test_foreign_buyer_and_other_taxes(self):
        p = build_issue_payload(move("E46", taxes=(0.0,), vat="PASS-1", country="US"))
        self.assertIsNone(p["buyerRnc"]); self.assertEqual(p["buyerForeignId"], "PASS-1")
        self.assertTrue(p["lines"][0]["exempt"])
        p = build_issue_payload(move("E32", taxes=(18.0, 10.0)))  # propina legal 10 %
        self.assertNotIn("totalAmount", p)


if __name__ == "__main__":
    unittest.main()
