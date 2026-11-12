#!/usr/bin/env python3
"""Fripick print gateway: runs next to the printers when Odoo is in the cloud. It pulls the queued jobs from Odoo with
the printer token, prints them on the local network and acknowledges each one. Standard library only (Python 3.9+):
works on Windows, macOS, Linux and Android (Termux). No inbound port is opened.

Config (environment or fripick-gateway.json next to this file):
  ODOO_URL        https://odoo.example.com
  FRIPICK_TOKEN   token of the printer (Odoo > Fripick > Impresoras)
  PRINTER_HOST    optional: overrides the printer IP configured in Odoo
  PRINTER_PORT    optional, default 9100 (raw ESC/POS)
  AGENT_URL       optional: POS Printing Suite agent (http://127.0.0.1:8085) for PDF jobs or USB printers
"""
import base64
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))


def load_config():
    cfg = {}
    path = os.path.join(HERE, "fripick-gateway.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            cfg.update(json.load(fh))
    for key in ("ODOO_URL", "FRIPICK_TOKEN", "PRINTER_HOST", "PRINTER_PORT", "AGENT_URL", "POLL_SECONDS"):
        if os.environ.get(key):
            cfg[key] = os.environ[key]
    if not cfg.get("ODOO_URL") or not cfg.get("FRIPICK_TOKEN"):
        sys.exit("Falta ODOO_URL o FRIPICK_TOKEN (variables de entorno o fripick-gateway.json)")
    return cfg


def call(cfg, path, body=None):
    req = urllib.request.Request(cfg["ODOO_URL"].rstrip("/") + path, method="POST" if body is not None else "GET",
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {cfg['FRIPICK_TOKEN']}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def print_job(cfg, printer, job):
    data = base64.b64decode(job["data"])
    if job["type"] == "pdf" or cfg.get("AGENT_URL"):
        agent = cfg.get("AGENT_URL") or "http://127.0.0.1:8085"
        body = json.dumps({"type": job["type"], "printer": printer.get("name", ""), "data": job["data"]}).encode()
        urllib.request.urlopen(urllib.request.Request(agent.rstrip("/") + "/print", data=body, method="POST",
                                                      headers={"Content-Type": "application/json"}), timeout=20).read()
        return
    host = cfg.get("PRINTER_HOST") or printer.get("host")
    port = int(cfg.get("PRINTER_PORT") or printer.get("port") or 9100)
    with socket.create_connection((host, port), timeout=10) as conn:
        conn.sendall(data)


def main():
    cfg = load_config()
    wait = float(cfg.get("POLL_SECONDS") or 3)
    print(f"Fripick gateway -> {cfg['ODOO_URL']} (cada {wait:g}s)", flush=True)
    while True:
        try:
            batch = call(cfg, "/fripick/gateway/jobs")
            for job in batch.get("jobs", []):
                try:
                    print_job(cfg, batch.get("printer", {}), job)
                    call(cfg, "/fripick/gateway/ack", {"id": job["id"], "ok": True})
                except Exception as exc:  # the job goes back to the queue in Odoo
                    call(cfg, "/fripick/gateway/ack", {"id": job["id"], "ok": False, "error": str(exc)[:200]})
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                sys.exit("Token rechazado por Odoo: revise FRIPICK_TOKEN")
            time.sleep(10)
        except Exception:  # network down: keep trying
            time.sleep(10)
        time.sleep(wait)


if __name__ == "__main__":
    main()
