from __future__ import annotations

import argparse
import asyncio
import ctypes
import json
import logging
import os
import platform
import shutil
import socket
import ssl
import base64
import subprocess
import sys
import threading
import tkinter as tk
import urllib.parse
import http.client
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from tkinter import messagebox, ttk
from typing import Optional, Tuple

try:
    import win32print  # type: ignore
    import requests
    from PIL import Image
    from PyPDF2 import PdfReader
except ImportError:
    win32print = None
    requests = None
    Image = None
    PdfReader = None

# Optional Windows service imports (only on Windows)
if os.name == "nt":
    try:
        import win32serviceutil  # type: ignore
        import win32service  # type: ignore
        import win32event  # type: ignore
        import servicemanager  # type: ignore
        import win32api  # type: ignore
        import win32con  # type: ignore
    except Exception:
        win32serviceutil = None  # type: ignore
        win32service = None  # type: ignore
        win32event = None  # type: ignore
        servicemanager = None  # type: ignore
        win32api = None  # type: ignore
        win32con = None  # type: ignore


# =========================================================
# CONFIG
# =========================================================

SERVICE_NAME = "LocalPrinterAgent"
DISPLAY_NAME = "LocalPrinterAgent"
SERVICE_DESC = "LocalPrinterAgent HTTP/HTTPS printing service for Odoo/POS."

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9060

ICON_RELATIVE_PATH = os.path.join("assets", "LocalPrinterAgent.ico")

AGENT_LOG_FILE = "agent.log"
GUI_LOG_FILE = "agent_gui.log"
SERVICE_CFG_FILE = "service_config.json"

CERT_FILE = "cert.pem"
KEY_FILE = "key.pem"
OPENSSL_DIR = "openssl"
OPENSSL_BINARY = "openssl.exe" if platform.system() == "Windows" else "openssl"
OPENSSL_DEFAULT_INSTALL_PATH = r"C:\Program Files\OpenSSL-Win64\bin\openssl.exe"

# Auth deshabilitada: token vacío para no requerir Authorization
AUTH_TOKEN = ""
USE_SSL = False
AGENT_VERSION = "1.0.0"

REQUIRED_PACKAGES = [
    ("pywin32", "win32print"),
    ("pillow", "PIL"),
    ("PyPDF2", "PyPDF2"),
    ("requests", "requests"),
]

# Runtime service options (populated from CLI when running as Windows Service host)
SERVICE_OPTS = {
    "host": DEFAULT_HOST,
    "port": DEFAULT_PORT,
    "use_ssl": USE_SSL,
}


# =========================================================
# SERVICE CONFIG (persist host/port)
# =========================================================

def cfg_path() -> str:
    return os.path.join(safe_app_dir(), SERVICE_CFG_FILE)


def save_service_config(host: str, port: int) -> None:
    data = {"host": host, "port": port}
    try:
        with open(cfg_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_service_config() -> tuple[str, int]:
    try:
        with open(cfg_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        host = str(data.get("host") or DEFAULT_HOST)
        port = int(data.get("port") or DEFAULT_PORT)
        return host, port
    except Exception:
        return DEFAULT_HOST, DEFAULT_PORT


# =========================================================
# COMMON UTILS
# =========================================================

def now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def run(cmd: list[str], cwd: Optional[str] = None, timeout: Optional[int] = None) -> Tuple[int, str]:
    kwargs = dict(capture_output=True, text=True, cwd=cwd, timeout=timeout)
    
    # Ocultar ventana CMD en Windows
    if is_windows():
        # CREATE_NO_WINDOW = 0x08000000
        kwargs["creationflags"] = 0x08000000
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE
        kwargs["startupinfo"] = si
    
    p = subprocess.run(cmd, **kwargs)
    out = (p.stdout or "") + "\n" + (p.stderr or "")
    return p.returncode, out.strip()


def http_response(status: int,
                  body: bytes = b"",
                  content_type: str = "application/json; charset=utf-8",
                  extra_headers: Optional[dict] = None) -> bytes:
    reason = {
        200: "OK",
        201: "Created",
        204: "No Content",
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        415: "Unsupported Media Type",
        500: "Internal Server Error",
    }.get(status, "OK")
    headers = {
        "Content-Type": content_type,
        "Content-Length": str(len(body)),
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Authorization, Content-Type",
        "Connection": "close",
    }
    if extra_headers:
        headers.update(extra_headers)
    head = [f"HTTP/1.1 {status} {reason}"] + [f"{k}: {v}" for k, v in headers.items()] + ["", ""]
    return ("\r\n".join(head)).encode("utf-8") + body


def is_windows() -> bool:
    return os.name == "nt"


def is_admin() -> bool:
    try:
        if os.name != "nt":
            return os.geteuid() == 0  # type: ignore[attr-defined]
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def relaunch_as_admin() -> bool:
    """
    Relaunch current process with UAC prompt. Returns True if ShellExecute was invoked.
    """
    try:
        params = " ".join([f'"{a}"' for a in sys.argv])
        rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
        return rc > 32
    except Exception:
        return False


def check_openssl_installed() -> bool:
    """Verifica si OpenSSL está instalado y accesible."""
    global OPENSSL_BINARY
    possible_paths = [
        OPENSSL_BINARY,
        OPENSSL_DEFAULT_INSTALL_PATH,
        os.path.join(os.getcwd(), OPENSSL_DIR, "Win64OpenSSL-3_4_1", "bin", "openssl.exe"),
    ]

    for path in possible_paths:
        try:
            result = subprocess.run([path, "version"], capture_output=True, text=True, check=True)
            logging.info(f"✅ OpenSSL encontrado en {path}: {result.stdout.strip()}")
            OPENSSL_BINARY = path
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, PermissionError):
            continue
    logging.warning("⚠️ OpenSSL no está instalado o no se encuentra en el PATH.")
    return False


def download_and_install_openssl() -> bool:
    """Descarga e instala OpenSSL automáticamente."""
    if check_openssl_installed():
        logging.info("✅ OpenSSL ya está instalado.")
        return True

    if not is_windows():
        logging.warning("⚠️ Descarga automática de OpenSSL solo en Windows.")
        return False

    try:
        logging.info("📥 Descargando OpenSSL...")
        url = "https://slproweb.com/download/Win64OpenSSL_Light-3_4_1.msi"
        openssl_msi = "Win64OpenSSL_Light-3_4_1.msi"
        
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        with open(openssl_msi, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        logging.info("📦 Instalando OpenSSL...")
        subprocess.run(["msiexec", "/i", openssl_msi, "/quiet", "/norestart"], check=True)
        os.remove(openssl_msi)
        logging.info("✅ OpenSSL instalado correctamente.")
        return check_openssl_installed()
    except Exception as e:
        logging.error(f"❌ Error instalando OpenSSL: {e}")
        return False


def module_exists(module_name: str) -> bool:
    try:
        __import__(module_name)
        return True
    except Exception:
        return False


def pip_install(package_name: str) -> Tuple[int, str]:
    return run([sys.executable, "-m", "pip", "install", "--upgrade", package_name])


def ensure_dependencies(log_fn) -> Tuple[bool, str]:
    missing = [(pkg, mod) for pkg, mod in REQUIRED_PACKAGES if not module_exists(mod)]
    if not missing:
        return True, "Dependencias OK."

    details = []
    for pkg, mod in missing:
        log_fn(f"Instalando dependencia: {pkg} (import {mod})")
        rc, out = pip_install(pkg)
        details.append(f"== pip install {pkg} ==\nRC={rc}\n{out}\n")
        if rc != 0:
            return False, "\n".join(details)

    still_missing = [(pkg, mod) for pkg, mod in REQUIRED_PACKAGES if not module_exists(mod)]
    if still_missing:
        return False, "Siguen faltando: " + ", ".join([m[0] for m in still_missing])

    return True, "\n".join(details)


def safe_app_dir() -> str:
    """
    Returns a stable directory for logs/assets:
    - If frozen: directory of exe
    - Else: directory of script
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def is_port_available(host: str, port: int) -> bool:
    target_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return sock.connect_ex((target_host, port)) != 0


# =========================================================
# WINDOWS SERVICE CONTROL (sc.exe)
# =========================================================

def sc(args: list[str]) -> Tuple[int, str]:
    return run(["sc"] + args)


def service_exists() -> bool:
    """Check if service is registered in Windows."""
    if not is_windows():
        return False
    rc, _out = sc(["query", SERVICE_NAME])
    return rc == 0


def service_state() -> str:
    """Try querying via pywin32; fallback to sc.exe parsing."""
    if is_windows() and win32serviceutil is not None and win32service is not None:
        try:
            st = win32serviceutil.QueryServiceStatus(SERVICE_NAME)  # type: ignore[attr-defined]
            cur = st[1]
            return {
                win32service.SERVICE_STOPPED: "STOPPED",
                win32service.SERVICE_START_PENDING: "START_PENDING",
                win32service.SERVICE_STOP_PENDING: "STOP_PENDING",
                win32service.SERVICE_RUNNING: "RUNNING",
            }.get(cur, f"UNKNOWN({cur})")
        except Exception:
            pass
    rc, out = sc(["query", SERVICE_NAME])
    if rc != 0:
        return "NOT_INSTALLED"
    if "RUNNING" in out:
        return "RUNNING"
    if "STOPPED" in out:
        return "STOPPED"
    if "START_PENDING" in out:
        return "START_PENDING"
    if "STOP_PENDING" in out:
        return "STOP_PENDING"
    return "UNKNOWN"


def get_service_binpath() -> str:
    rc, out = sc(["qc", SERVICE_NAME])
    if rc != 0:
        return ""
    for line in out.splitlines():
        if "BINARY_PATH_NAME" in line:
            return line.split(":", 1)[-1].strip()
    return ""


def configure_service_recovery() -> Tuple[bool, str]:
    """
    Restart on failure (3 times), reset daily.
    """
    rc1, out1 = sc(["failure", SERVICE_NAME, "reset=", "86400", "actions=", "restart/5000/restart/5000/restart/5000"])
    rc2, out2 = sc(["failureflag", SERVICE_NAME, "1"])
    ok = (rc1 == 0 and rc2 == 0)
    return ok, (out1 + "\n" + out2).strip()


def install_or_update_service(host: str, port: int, log_fn) -> Tuple[bool, str]:
    """
    Install/update a REAL Windows Service using pywin32's ServiceFramework.
    Avoids 1053 by registering with SCM properly.
    """
    if not (is_windows() and win32serviceutil is not None):
        return False, "Solo Windows soportado para servicio (pywin32 no disponible)."

    # Persist config so the service can read host/port at runtime
    save_service_config(host, port)

    # Use pywin32 install/update verbs through this same module
    base = [sys.executable]
    if not getattr(sys, "frozen", False):
        base.append(os.path.abspath(__file__))

    # Try install first, then update if exists
    rc_i, out_i = run(base + ["install", "--startup=delayed"])
    if rc_i != 0:
        rc_u, out_u = run(base + ["update", "--startup=delayed"])
        if rc_u != 0:
            return False, (out_i + "\n" + out_u).strip()
        log_fn("Servicio actualizado (pywin32).")
    else:
        log_fn("Servicio instalado (pywin32).")

    # Description is handled by the service class; ChangeServiceConfig2 is internal to pywin32
    return True, "Servicio instalado/actualizado (pywin32)"


def start_service() -> Tuple[bool, str]:
    base = [sys.executable]
    if not getattr(sys, "frozen", False):
        base.append(os.path.abspath(__file__))
    rc, out = run(base + ["start"])
    return rc == 0, out


def stop_service() -> Tuple[bool, str]:
    base = [sys.executable]
    if not getattr(sys, "frozen", False):
        base.append(os.path.abspath(__file__))
    rc, out = run(base + ["stop"])
    return rc == 0, out


def delete_service() -> Tuple[bool, str]:
    base = [sys.executable]
    if not getattr(sys, "frozen", False):
        base.append(os.path.abspath(__file__))
    rc, out = run(base + ["remove"])
    return rc == 0, out


# =========================================================
# FIREWALL (optional)
# =========================================================

def open_firewall_port(port: int) -> Tuple[bool, str]:
    rule_name = f"{SERVICE_NAME} TCP {port}"
    cmd = [
        "netsh", "advfirewall", "firewall", "add", "rule",
        f"name={rule_name}",
        "dir=in",
        "action=allow",
        "protocol=TCP",
        f"localport={port}",
    ]
    rc, out = run(cmd)
    return rc == 0, out


# =========================================================
# AGENT (WEBSOCKET + PRINTERS)
# =========================================================

def configure_agent_logging(app_dir: str, level: str = "INFO") -> logging.Logger:
    log_path = os.path.join(app_dir, AGENT_LOG_FILE)
    logger = logging.getLogger("LocalPrinterAgent")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    # Avoid duplicate handlers if service restarts
    if not logger.handlers:
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger


def list_system_printers(logger: logging.Logger) -> dict:
    system = platform.system()
    try:
        if system == "Windows":
            import win32print  # type: ignore
            # Incluir tanto impresoras locales como conexiones de red
            printers = [p[2] for p in win32print.EnumPrinters(
                win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            )]
            return {"status": "success", "printers": printers}
        if system == "Linux":
            if shutil.which("lpstat") is None:
                return {"status": "error", "message": "lpstat no disponible"}
            out = subprocess.check_output(["lpstat", "-p", "-d"], text=True, timeout=10)
            printers = [line.split()[1] for line in out.splitlines() if line.startswith("printer ")]
            return {"status": "success", "printers": printers}
        return {"status": "error", "message": f"OS no soportado: {system}"}
    except Exception as exc:
        logger.exception("Error listando impresoras: %s", exc)
        return {"status": "error", "message": str(exc)}


def print_receipt_windows_raw(printer_name: str, raw_data: str, logger: logging.Logger) -> dict:
    """
    RAW printing via win32print (Windows).
    """
    try:
        import win32print  # type: ignore

        h_printer = win32print.OpenPrinter(printer_name)
        try:
            h_job = win32print.StartDocPrinter(h_printer, 1, ("Odoo Receipt", None, "RAW"))
            try:
                win32print.StartPagePrinter(h_printer)
                win32print.WritePrinter(h_printer, raw_data.encode("utf-8", errors="replace"))
                win32print.EndPagePrinter(h_printer)
            finally:
                win32print.EndDocPrinter(h_printer)
        finally:
            win32print.ClosePrinter(h_printer)

        return {"status": "success", "message": "Print job sent."}
    except Exception as exc:
        logger.exception("Fallo imprimiendo: %s", exc)
        return {"status": "error", "message": str(exc)}


def get_available_printers(logger: logging.Logger) -> list:
    """Retorna lista de impresoras disponibles."""
    try:
        if platform.system() == "Windows" and win32print:
            return [p[2] for p in win32print.EnumPrinters(2)]
        return []
    except Exception as e:
        logger.error(f"❌ Error listando impresoras: {e}")
        return []


def print_data(printer_name: str, data: bytes, logger: logging.Logger) -> bool:
    """Imprime datos RAW."""
    try:
        if not win32print or not is_windows():
            logger.error("❌ Impresión solo disponible en Windows con win32print")
            return False
        
        hprinter = win32print.OpenPrinter(printer_name)
        job = win32print.StartDocPrinter(hprinter, 1, ("Print Job", None, "RAW"))
        win32print.StartPagePrinter(hprinter)
        win32print.WritePrinter(hprinter, data)
        win32print.EndPagePrinter(hprinter)
        win32print.EndDocPrinter(hprinter)
        win32print.ClosePrinter(hprinter)
        logger.info("✅ Impresión completada correctamente")
        return True
    except Exception as e:
        logger.error(f"❌ Error al imprimir: {e}")
        return False


def print_pdf(printer_name: str, data: bytes, logger: logging.Logger) -> bool:
    """Imprime PDF."""
    try:
        if not PdfReader:
            logger.error("❌ PyPDF2 no disponible")
            return False
        
        with BytesIO(data) as f:
            reader = PdfReader(f)
            text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
            return print_data(printer_name, text.encode("utf-8"), logger)
    except Exception as e:
        logger.error(f"❌ Error al imprimir PDF: {e}")
        return False


def print_image(printer_name: str, data: bytes, logger: logging.Logger) -> bool:
    """Imprime imagen."""
    try:
        if not Image:
            logger.error("❌ PIL no disponible")
            return False
        
        with BytesIO(data) as f:
            img = Image.open(f)
            img = img.convert('RGB')
            raw_data = img.tobytes()
            return print_data(printer_name, raw_data, logger)
    except Exception as e:
        logger.error(f"❌ Error al imprimir imagen: {e}")
        return False


def generate_ssl_cert(logger: logging.Logger) -> bool:
    """Genera certificados SSL."""
    if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
        logger.info("✅ Certificados SSL ya existen")
        return True

    if not check_openssl_installed():
        if not download_and_install_openssl():
            logger.error("❌ No se pudo instalar OpenSSL")
            return False

    try:
        logger.info("🔒 Generando certificado SSL...")
        
        openssl_conf = """[req]
distinguished_name = req_distinguished_name
x509_extensions = v3_req
prompt = no

[req_distinguished_name]
CN = 127.0.0.1

[v3_req]
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
IP.1 = 127.0.0.1
"""
        conf_file = "openssl-san.conf"
        with open(conf_file, "w") as f:
            f.write(openssl_conf)

        subprocess.run([
            OPENSSL_BINARY, "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", KEY_FILE, "-out", CERT_FILE, "-days", "365", "-nodes",
            "-config", conf_file
        ], check=True, capture_output=True)

        os.remove(conf_file)
        logger.info("✅ Certificado SSL generado correctamente")
        return True
    except Exception as e:
        logger.error(f"❌ Error generando SSL: {e}")
        return False


def handle_client(client_socket: socket.socket, logger: logging.Logger, selected_printer: str, use_ssl: bool):
    """Maneja conexiones de clientes HTTP/HTTPS."""
    try:
        client_socket.settimeout(10)
        
        if use_ssl:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
            client_socket = context.wrap_socket(client_socket, server_side=True)
        
        # Read initial bytes
        data = client_socket.recv(8192)
        if not data:
            logger.warning("⚠️ No se recibieron datos")
            return

        # Split headers/body
        header_end = data.find(b"\r\n\r\n")
        while header_end == -1 and len(data) < 1024 * 1024:
            # keep reading headers (guard up to 1MB)
            chunk = client_socket.recv(8192)
            if not chunk:
                break
            data += chunk
            header_end = data.find(b"\r\n\r\n")

        if header_end == -1:
            logger.warning("⚠️ Solicitud sin fin de cabeceras")
            client_socket.send(http_response(400, b""))
            return

        header_bytes = data[:header_end]
        body = data[header_end + 4:]

        request_str = header_bytes.decode('utf-8', errors='ignore')
        lines = request_str.split('\r\n')
        if not lines:
            client_socket.send(http_response(400, b""))
            return

        request_line = lines[0].split()
        if len(request_line) < 3:
            client_socket.send(http_response(400, b""))
            return

        method, path, _ = request_line
        logger.info(f"📋 Método: {method}, Ruta: {path}")

        # Parse headers
        headers = {}
        for h in lines[1:]:
            if not h:
                continue
            if ":" in h:
                k, v = h.split(":", 1)
                headers[k.strip().lower()] = v.strip()

        # If Content-Length present, read full body
        try:
            if 'content-length' in headers:
                total = int(headers['content-length'])
                missing = total - len(body)
                while missing > 0:
                    chunk = client_socket.recv(min(65536, missing))
                    if not chunk:
                        break
                    body += chunk
                    missing -= len(chunk)
        except Exception:
            pass

        # Preflight CORS
        if method == "OPTIONS":
            client_socket.send(http_response(200, b"", content_type="text/plain"))
            return

        parsed_url = urllib.parse.urlparse(path)
        query_params = urllib.parse.parse_qs(parsed_url.query)

        # REST endpoints
        if parsed_url.path == "/health" and method == "GET":
            payload = json.dumps({"status": "ok", "version": AGENT_VERSION}).encode("utf-8")
            client_socket.send(http_response(200, payload))
            return

        if parsed_url.path == "/printers" and method == "GET":
            printers = get_available_printers(logger)
            payload = json.dumps({"status": "ok", "printers": printers}).encode("utf-8")
            client_socket.send(http_response(200, payload))
            return

        if parsed_url.path == "/print" and method == "POST":
            # Auth (optional)
            if AUTH_TOKEN:
                auth = headers.get('authorization', '')
                if not auth.startswith('Bearer ') or auth.split(' ', 1)[1] != AUTH_TOKEN:
                    client_socket.send(http_response(403, json.dumps({"error": "Invalid Token"}).encode("utf-8")))
                    return

            ctype = headers.get('content-type', '')
            try:
                req = {}
                if ctype.startswith('application/json'):
                    req = json.loads(body.decode('utf-8', errors='ignore') or '{}')
                else:
                    # Fallback: treat as raw text to selected_printer
                    req = {"type": "raw", "printer": selected_printer, "data": base64.b64encode(body).decode('ascii')}

                ptype = (req.get('type') or 'raw').lower()
                printer = (req.get('printer') or selected_printer or '').strip()
                data_b64 = req.get('data')
                if not printer:
                    client_socket.send(http_response(400, json.dumps({"error": "Missing printer"}).encode("utf-8")))
                    return
                if not data_b64:
                    client_socket.send(http_response(400, json.dumps({"error": "Missing data"}).encode("utf-8")))
                    return
                blob = base64.b64decode(data_b64)

                if ptype == 'pdf':
                    ok = print_pdf(printer, blob, logger)
                elif ptype == 'image':
                    ok = print_image(printer, blob, logger)
                else:
                    ok = print_data(printer, blob, logger)

                resp = {"status": "ok" if ok else "error"}
                client_socket.send(http_response(200 if ok else 500, json.dumps(resp).encode("utf-8")))
            except Exception as e:
                logger.error(f"❌ Error /print: {e}")
                client_socket.send(http_response(500, json.dumps({"error": str(e)}).encode("utf-8")))
            return

        # Legacy Epson-like endpoint
        if parsed_url.path != "/cgi-bin/epos/service.cgi":
            client_socket.send(http_response(404, b""))
            return

        devid = query_params.get('devid', [None])[0]
        if devid != "local_printer":
            response = b"HTTP/1.1 400 Bad Request\r\nContent-Length: 12\r\n\r\nInvalid devid"
            client_socket.send(response)
            return

        # Separar headers del body
        try:
            headers_data, body = data.split(b"\r\n\r\n", 1)
        except ValueError:
            body = b""

        # Verificar autenticación (legacy flow usa token si se configura)
        if AUTH_TOKEN:
            auth = headers.get('authorization', '')
            if not auth.startswith('Bearer ') or auth.split(' ', 1)[1] != AUTH_TOKEN:
                client_socket.send(http_response(403, json.dumps({"error": "Invalid Token"}).encode("utf-8")))
                return

        # Procesar impresión según tipo
        if body[:4] == b"%PDF":
            logger.info("📄 Procesando PDF...")
            success = print_pdf(selected_printer, body, logger)
        elif body[:2] == b"\xff\xd8":
            logger.info("🖼️ Procesando imagen...")
            success = print_image(selected_printer, body, logger)
        else:
            logger.info("📝 Procesando datos de texto...")
            success = print_data(selected_printer, body, logger)

        response_body = b"Print completed" if success else b"Print failed"
        client_socket.send(http_response(200 if success else 500, response_body, content_type="text/plain"))
        logger.info("✅ Respuesta enviada")

    except ssl.SSLError as e:
        logger.error(f"❌ Error SSL: {e}")
    except socket.timeout:
        logger.error("❌ Timeout")
    except Exception as e:
        logger.error(f"❌ Error en conexión: {e}")
    finally:
        try:
            client_socket.close()
        except:
            pass


def run_http_server(host: str, port: int, logger: logging.Logger, selected_printer: str, use_ssl: bool):
    """Ejecuta servidor HTTP/HTTPS."""
    if use_ssl:
        if not generate_ssl_cert(logger):
            logger.error("❌ No se pudo generar certificado SSL")
            return

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((host, port))
        server_socket.listen(5)

        protocol = "HTTPS" if use_ssl else "HTTP"
        logger.info(f"🖨️ Servidor {protocol} corriendo en {protocol.lower()}://{host}:{port}")

        while True:
            try:
                server_socket.settimeout(1)
                client_socket, addr = server_socket.accept()
                logger.info(f"📡 Nueva conexión desde {addr}")
                threading.Thread(
                    target=handle_client,
                    args=(client_socket, logger, selected_printer, use_ssl),
                    daemon=True
                ).start()
            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"❌ Error: {e}")
                break


def run_agent_service(host: str, port: int, selected_printer: str, use_ssl: bool = True):
    app_dir = safe_app_dir()
    logger = configure_agent_logging(app_dir, "INFO")

    ok, details = ensure_dependencies(logger.info)
    if not ok:
        logger.error("Dependencias no instaladas:\n%s", details)
        raise SystemExit(2)

    try:
        run_http_server(host, port, logger, selected_printer, use_ssl)
    except Exception as exc:
        logger.exception("Agent crashed: %s", exc)
        raise


# =========================================================
# WINDOWS SERVICE (pywin32) — real service to satisfy SCM
# =========================================================
if is_windows() and win32serviceutil is not None and win32service is not None:
    class LocalPrinterAgentService(win32serviceutil.ServiceFramework):  # type: ignore[misc]
        _svc_name_ = SERVICE_NAME
        _svc_display_name_ = DISPLAY_NAME
        _svc_description_ = SERVICE_DESC

        def __init__(self, args):
            super().__init__(args)
            self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)  # type: ignore[arg-type]
            self.loop: Optional[asyncio.AbstractEventLoop] = None
            self.stop_event_async: Optional[asyncio.Event] = None

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self.hWaitStop)
            if self.loop and self.stop_event_async:
                try:
                    self.loop.call_soon_threadsafe(self.stop_event_async.set)
                except Exception:
                    pass

        def SvcDoRun(self):
            app_dir = safe_app_dir()
            logger = configure_agent_logging(app_dir, "INFO")

            try:
                ok, details = ensure_dependencies(logger.info)
                if not ok:
                    logger.error("Dependencias no instaladas:\n%s", details)
                    if servicemanager:
                        servicemanager.LogErrorMsg("Dependencias no instaladas. Ver agent.log.")
                    return

                host, port = load_service_config()
                config_data = {}
                if os.path.exists(cfg_path()):
                    try:
                        with open(cfg_path()) as f:
                            config_data = json.load(f)
                    except:
                        pass
                
                selected_printer = config_data.get("printer", "")
                use_ssl = config_data.get("use_ssl", True)
                
                logger.info("Servicio iniciando con host=%s port=%s printer=%s ssl=%s", host, port, selected_printer, use_ssl)

                if servicemanager:
                    servicemanager.LogMsg(
                        servicemanager.EVENTLOG_INFORMATION_TYPE,
                        servicemanager.PYS_SERVICE_STARTED,
                        (self._svc_name_, ""),
                    )

                run_http_server(host, port, logger, selected_printer, use_ssl)

            except Exception as exc:
                logger.exception("Service crashed: %s", exc)
                if servicemanager:
                    servicemanager.LogErrorMsg(f"Service crashed: {exc}")


# =========================================================
# GUI
# =========================================================

@dataclass(frozen=True)
class GuiPaths:
    base: str
    icon: str
    agent_log: str
    gui_log: str


def gui_paths() -> GuiPaths:
    base = safe_app_dir()
    return GuiPaths(
        base=base,
        icon=os.path.join(base, ICON_RELATIVE_PATH),
        agent_log=os.path.join(base, AGENT_LOG_FILE),
        gui_log=os.path.join(base, GUI_LOG_FILE),
    )


class AgentGUI(tk.Tk):
    def __init__(self, tray_mode: bool = False):
        super().__init__()
        self.paths = gui_paths()
        self.tray_mode = tray_mode
        self.selected_printer = ""
        self.proxy_running = False

        self.title("LocalPrinterAgent - Proxy HTTP/HTTPS")
        self.geometry("500x400")
        self.resizable(False, False)

        try:
            if os.path.exists(self.paths.icon):
                self.iconbitmap(self.paths.icon)
        except Exception:
            pass

        self.host_var = tk.StringVar(value=DEFAULT_HOST)
        self.port_var = tk.StringVar(value=str(DEFAULT_PORT))
        self.ssl_var = tk.BooleanVar(value=USE_SSL)

        self._build_ui()
        self.log("GUI iniciado.")
        self.load_config()
        self.refresh_printers()

    def log(self, msg: str):
        line = f"{now_ts()} | {msg}\n"
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        # persist minimal GUI log
        try:
            with open(self.paths.gui_log, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass

    def clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def require_admin_or_relaunch(self, reason: str) -> bool:
        if is_admin():
            return True

        self.log(f"Se requiere Administrador para: {reason}. Solicitando UAC...")
        
        # Intentar relanzar con permisos de admin
        try:
            ok = relaunch_as_admin()
            if ok:
                self.log("UAC solicitado exitosamente. Se ha lanzado una nueva instancia con permisos.")
                messagebox.showinfo(
                    "Elevación de permisos",
                    "Se ha abierto una nueva ventana con permisos de Administrador.\n"
                    "Por favor, continúa en esa ventana. Puedes cerrar esta ventana cuando termine."
                )
                # NO destruir automáticamente - mantener GUI abierta
                return False
            else:
                self.log("UAC cancelado o no disponible.")
                messagebox.showwarning(
                    "UAC cancelado",
                    f"Para {reason} se requieren permisos de Administrador.\n\n"
                    f"Hiciste clic 'No' en el diálogo de UAC.\n"
                    f"Puedes reintentar o ejecutar como Administrador."
                )
                return False
        except Exception as exc:
            self.log(f"Error al solicitar UAC: {exc}")
            messagebox.showerror("Error", f"No se pudo solicitar permisos: {exc}")
            return False

    def parse_host_port(self) -> tuple[str, int]:
        host = self.host_var.get().strip() or DEFAULT_HOST
        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            raise ValueError("Puerto inválido. Debe ser número.")
        if not (1 <= port <= 65535):
            raise ValueError("Puerto inválido. Rango 1..65535.")
        return host, port

    def _build_ui(self):
        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, padx=10, pady=10)

        ttk.Label(frm, text="LocalPrinterAgent - Proxy HTTP/HTTPS", font=("Segoe UI", 14, "bold")).pack(pady=10)

        # Configuration Frame
        cfg_frm = ttk.LabelFrame(frm, text="Configuración", padding=10)
        cfg_frm.pack(fill="x", pady=5)

        ttk.Label(cfg_frm, text="Host:").pack(anchor="w")
        ttk.Entry(cfg_frm, textvariable=self.host_var, width=40).pack(anchor="w", pady=2)

        ttk.Label(cfg_frm, text="Puerto:").pack(anchor="w")
        ttk.Entry(cfg_frm, textvariable=self.port_var, width=40).pack(anchor="w", pady=2)

        ttk.Label(cfg_frm, text="Impresora:").pack(anchor="w")
        self.printer_dropdown = ttk.Combobox(cfg_frm, state="readonly", width=37)
        self.printer_dropdown.pack(anchor="w", pady=2)
        self.printer_dropdown.bind("<<ComboboxSelected>>", self.on_printer_selected)

        ttk.Checkbutton(cfg_frm, text="Usar HTTPS (recomendado)", variable=self.ssl_var, command=self.on_ssl_toggle).pack(anchor="w", pady=5)

        # Buttons Frame
        btn_frm = ttk.Frame(frm)
        btn_frm.pack(fill="x", pady=10)

        ttk.Button(btn_frm, text="Instalar Deps", command=self.on_deps, width=15).pack(side="left", padx=2)
        ttk.Button(btn_frm, text="Iniciar", command=self.on_start, width=15).pack(side="left", padx=2)
        ttk.Button(btn_frm, text="Detener", command=self.on_stop, width=15).pack(side="left", padx=2)

        # Log Frame
        log_frm = ttk.LabelFrame(frm, text="Log", padding=5)
        log_frm.pack(fill="both", expand=True, pady=5)

        self.log_text = tk.Text(log_frm, height=12, wrap="word", state="disabled")
        scroll = ttk.Scrollbar(log_frm, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)

        self.log_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def refresh_printers(self):
        """Actualiza lista de impresoras."""
        app_dir = safe_app_dir()
        logger = configure_agent_logging(app_dir, "INFO")
        printers = get_available_printers(logger)
        self.printer_dropdown["values"] = printers
        if self.selected_printer in printers:
            self.printer_dropdown.set(self.selected_printer)
        elif printers:
            self.printer_dropdown.set(printers[0])
            self.selected_printer = printers[0]

    def load_config(self):
        """Carga configuración guardada."""
        if os.path.exists(cfg_path()):
            try:
                with open(cfg_path()) as f:
                    config = json.load(f)
                self.host_var.set(config.get("host", DEFAULT_HOST))
                self.port_var.set(config.get("port", DEFAULT_PORT))
                self.selected_printer = config.get("printer", "")
                self.ssl_var.set(config.get("use_ssl", USE_SSL))
            except:
                pass

    def save_config(self):
        """Guarda configuración."""
        config = {
            "host": self.host_var.get().strip(),
            "port": self.port_var.get().strip(),
            "printer": self.selected_printer,
            "use_ssl": self.ssl_var.get(),
        }
        try:
            with open(cfg_path(), "w") as f:
                json.dump(config, f, indent=4)
            self.log("✅ Configuración guardada")
        except Exception as e:
            self.log(f"❌ Error guardando config: {e}")

    def on_printer_selected(self, event):
        """Evento cuando se selecciona impresora."""
        self.selected_printer = self.printer_dropdown.get()
        self.save_config()
        self.log(f"🖨️ Impresora seleccionada: {self.selected_printer}")

    def on_ssl_toggle(self):
        """Toggle SSL mode."""
        self.save_config()
        mode = "HTTPS" if self.ssl_var.get() else "HTTP"
        self.log(f"🔒 Modo: {mode}")
        if not self.ssl_var.get():
            messagebox.showwarning("Advertencia", "HTTP no es seguro. Se recomienda HTTPS.")

    def on_deps(self):
        """Instala dependencias."""
        self.log("📥 Instalando dependencias en segundo plano...")
        
        def task():
            try:
                ok, details = ensure_dependencies(self.log)
                self.log(f"{'✅' if ok else '❌'} Instalación: {'OK' if ok else 'FAILED'}")
                if not ok:
                    self.after(0, lambda: messagebox.showerror("Error", details))
            except Exception as e:
                self.log(f"❌ Error: {e}")
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
        
        thread = threading.Thread(target=task, daemon=True)
        thread.start()

    def on_start(self):
        """Inicia el proxy."""
        if not self.selected_printer:
            messagebox.showerror("Error", "Debe seleccionar una impresora.")
            return

        try:
            host = self.host_var.get().strip()
            port = int(self.port_var.get().strip())
            use_ssl = self.ssl_var.get()
        except ValueError:
            messagebox.showerror("Error", "IP o puerto inválido.")
            return

        if use_ssl and not is_admin():
            if not self.require_admin_or_relaunch("usar HTTPS"):
                return

        self.save_config()
        self.log(f"🚀 Iniciando proxy en {host}:{port}...")
        self.log(f"🖨️ Impresora: {self.selected_printer}")
        self.log(f"🔒 SSL: {'Activado' if use_ssl else 'Desactivado'}")

        def task():
            try:
                run_http_server(host, port, logging.getLogger("LocalPrinterAgent"), self.selected_printer, use_ssl)
            except Exception as e:
                self.log(f"❌ Error: {e}")
                self.after(0, lambda: messagebox.showerror("Error", str(e)))

        thread = threading.Thread(target=task, daemon=True)
        thread.start()
        messagebox.showinfo("Iniciado", f"Proxy iniciado en {host}:{port}")

    def on_stop(self):
        """Detiene el proxy."""
        self.log("🛑 Deteniendo proxy...")
        messagebox.showinfo("Detenido", "Proxy detenido")


# =========================================================
# ARGUMENTS / MAIN
# =========================================================

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="LocalPrinterAgent (Windows Service + GUI, WS sin SSL)")
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    return p.parse_args()


def main() -> None:
    if not is_windows():
        messagebox.showerror("Windows requerido", "Este programa está diseñado para Windows.")
        raise SystemExit(1)

    # If invoked with pywin32 verbs, persist config and delegate to HandleCommandLine
    if len(sys.argv) >= 2 and sys.argv[1].lower() in {"install", "update", "remove", "start", "stop", "restart"}:
        args = parse_args()
        save_service_config(args.host, args.port)
        if win32serviceutil is None:
            print("pywin32 no disponible. No se puede gestionar el servicio.")
            raise SystemExit(1)
        win32serviceutil.HandleCommandLine(LocalPrinterAgentService)  # type: ignore[name-defined]
        return

    # GUI mode
    app = AgentGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
