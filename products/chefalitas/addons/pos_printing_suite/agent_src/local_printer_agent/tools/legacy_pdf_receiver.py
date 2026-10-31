#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dev receiver for local POS print tests.

Endpoints:
- GET /health
- GET /printers
- POST /print

Behavior:
- Receives base64 payloads from POS local-agent flow.
- Saves image payload to PNG and also exports a PDF copy (when Pillow is available).
"""

from __future__ import annotations

import base64
import json
import os
import re
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    from PIL import Image
except Exception:
    Image = None


HOST = os.environ.get("POS_RECEIVER_HOST", "127.0.0.1")
PORT = int(os.environ.get("POS_RECEIVER_PORT", "9060"))
OUT_DIR = os.environ.get("POS_RECEIVER_OUT", os.path.join("tmp", "print_jobs"))
os.makedirs(OUT_DIR, exist_ok=True)


def _tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def _strip_data_url(value: str) -> str:
    if not isinstance(value, str):
        return ""
    match = re.match(r"^data:[^;]+;base64,(.*)$", value, flags=re.I | re.S)
    return match.group(1) if match else value


def _save_image_payload(data_b64: str) -> dict:
    raw = base64.b64decode(_strip_data_url(data_b64), validate=False)
    png_path = os.path.join(OUT_DIR, f"job_{_tag()}.png")
    with open(png_path, "wb") as handle:
        handle.write(raw)
    result = {"png": png_path}
    if Image:
        try:
            img = Image.open(png_path).convert("RGB")
            pdf_path = png_path[:-4] + ".pdf"
            img.save(pdf_path, "PDF", resolution=203)
            result["pdf"] = pdf_path
        except Exception as exc:
            result["pdf_error"] = str(exc)
    return result


def _save_pdf_payload(data_b64: str) -> str:
    raw = base64.b64decode(_strip_data_url(data_b64), validate=False)
    pdf_path = os.path.join(OUT_DIR, f"job_{_tag()}.pdf")
    with open(pdf_path, "wb") as handle:
        handle.write(raw)
    return pdf_path


class Handler(BaseHTTPRequestHandler):
    def _set_cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Private-Network", "true")

    def _send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self._set_cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._set_cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/health":
            return self._send_json(200, {"status": "ok"})
        if self.path == "/printers":
            return self._send_json(200, {"printers": ["PDF"]})
        return self._send_json(404, {"error": "not found", "path": self.path})

    def do_POST(self) -> None:
        if self.path != "/print":
            return self._send_json(404, {"error": "not found", "path": self.path})
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return self._send_json(400, {"error": "missing body"})
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            return self._send_json(400, {"error": "invalid json"})

        typ = str(data.get("type") or "image").lower()
        payload = data.get("data")
        if not payload:
            return self._send_json(400, {"error": "data required"})

        if typ == "pdf":
            saved = _save_pdf_payload(payload)
        else:
            saved = _save_image_payload(payload)
        return self._send_json(200, {"ok": True, "type": typ, "saved": saved})


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Legacy PDF receiver listening on http://{HOST}:{PORT}")
    print(f"Saving jobs into: {OUT_DIR}")
    server.serve_forever()


if __name__ == "__main__":
    main()

