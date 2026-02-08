# -*- coding: utf-8 -*-
"""
Local Printer Agent: HTTP server (no GUI).
Endpoints: GET /health, GET /printers, POST /print.
Auth: Authorization: Bearer <token> for /print (and optionally /printers).
Config from ProgramData (config.json). Logs to file.
"""
import json
import logging
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

from config_loader import load_config, VERSION, DEFAULT_HOST, DEFAULT_PORT
from printer_backends import list_printers, resolve_printer_name, print_raw, print_pdf, print_image

# Ensure no GUI imports
assert "tkinter" not in sys.modules, "GUI not allowed in service"

logger = None

try:
    from http.server import ThreadingHTTPServer as _ThreadingHTTPServer
except Exception:
    _ThreadingHTTPServer = HTTPServer


def setup_logging(log_dir):
    global logger
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "agent.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )
    logger = logging.getLogger(__name__)
    return logger


class Handler(BaseHTTPRequestHandler):
    config = None

    def log_message(self, format, *args):
        if logger:
            logger.info("%s - %s", self.address_string(), format % args)

    def _send_json(self, status, body):
        self.send_response(status)
        self._set_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode("utf-8"))

    def _set_cors_headers(self):
        # Allow browser POS to call local agent with Authorization header.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")
        # Allow Private Network Access (Chrome/Edge) from HTTPS POS to localhost agent.
        self.send_header("Access-Control-Allow-Private-Network", "true")

    def _check_auth(self):
        # If no token is configured, allow local usage without auth.
        if not (self.config.get("token") or "").strip():
            return True
        auth = self.headers.get("Authorization")
        if not auth or not auth.startswith("Bearer "):
            return False
        token = auth[7:].strip()
        return token and token == (self.config.get("token") or "")

    def do_OPTIONS(self):
        self.send_response(204)
        self._set_cors_headers()
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {"status": "ok", "version": VERSION})
            return
        if self.path == "/printers":
            try:
                names = list_printers()
                self._send_json(200, {"printers": names})
            except Exception as e:
                logger.exception("list printers")
                self._send_json(500, {"error": str(e)})
            return
        self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        if self.path != "/print":
            self._send_json(404, {"error": "Not found"})
            return
        if not self._check_auth():
            self._send_json(401, {"error": "Unauthorized"})
            return
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length <= 0:
            self._send_json(400, {"error": "Missing body"})
            return
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body.decode("utf-8"))
        except Exception as e:
            self._send_json(400, {"error": f"Invalid JSON: {e}"})
            return
        printer_name = data.get("printer") or data.get("printerName")
        typ = (data.get("type") or "raw").lower()
        payload_b64 = data.get("data")
        if not printer_name or not payload_b64:
            self._send_json(400, {"error": "printer and data required"})
            return
        try:
            printer_name = resolve_printer_name(printer_name)
            if typ == "raw":
                print_raw(printer_name, payload_b64)
            elif typ == "pdf":
                print_pdf(printer_name, payload_b64)
            elif typ == "image":
                print_image(printer_name, payload_b64)
            else:
                self._send_json(400, {"error": f"Unknown type: {typ}"})
                return
            self._send_json(200, {"ok": True})
        except Exception as e:
            logger.exception("print")
            self._send_json(500, {"error": str(e)})


def run_server(config=None):
    if config is None:
        config = load_config()
    setup_logging(config.get("log_dir", ""))
    host = config.get("host", DEFAULT_HOST)
    port = int(config.get("port", DEFAULT_PORT))
    Handler.config = config
    server = _ThreadingHTTPServer((host, port), Handler)
    logger.info("Local Printer Agent listening on %s:%s", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down")
    finally:
        server.server_close()


if __name__ == "__main__":
    run_server()
