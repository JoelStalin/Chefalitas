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
import subprocess
import sys
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Optional, Tuple


# =========================================================
# CONFIG
# =========================================================

SERVICE_NAME = "LocalPrinterAgent"
DISPLAY_NAME = "LocalPrinterAgent"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9089

ICON_RELATIVE_PATH = os.path.join("assets", "LocalPrinterAgent.ico")

AGENT_LOG_FILE = "agent.log"
GUI_LOG_FILE = "agent_gui.log"

REQUIRED_PACKAGES = [
    ("websockets", "websockets"),
    ("pywin32", "win32print"),
]

WEBSOCKET_COMMANDS = {"health", "list_printers", "print_receipt"}


# =========================================================
# COMMON UTILS
# =========================================================

def now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def run(cmd: list[str], cwd: Optional[str] = None, timeout: Optional[int] = None) -> Tuple[int, str]:
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout)
    out = (p.stdout or "") + "\n" + (p.stderr or "")
    return p.returncode, out.strip()


def is_windows() -> bool:
    return os.name == "nt"


def is_admin() -> bool:
    try:
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


def service_state() -> str:
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
    Service binPath points to THIS SAME executable/script with `--service`.
    That prevents opening the GUI when the service starts.
    """
    # Prefer the current executable for service.
    # If not frozen, it will run python.exe with this script.
    # Best practice: compile with PyInstaller --noconsole to avoid any console.
    if getattr(sys, "frozen", False):
        exe = os.path.abspath(sys.executable)
        bin_path = f'"{exe}" --service --host "{host}" --port {port}'
    else:
        py = os.path.abspath(sys.executable)
        script = os.path.abspath(__file__)
        # Use pythonw if available to reduce windows when launching service
        pyw = py
        if is_windows() and os.path.basename(py).lower() == "python.exe":
            cand = os.path.join(os.path.dirname(py), "pythonw.exe")
            if os.path.exists(cand):
                pyw = cand
        bin_path = f'"{pyw}" "{script}" --service --host "{host}" --port {port}'

    log_fn(f"binPath servicio: {bin_path}")

    st = service_state()
    if st == "NOT_INSTALLED":
        rc, out = sc(["create", SERVICE_NAME, "binPath=", bin_path, "start=", "auto", "DisplayName=", DISPLAY_NAME])
        if rc != 0:
            return False, out
        sc(["description", SERVICE_NAME, "LocalPrinterAgent WebSocket printing service for Odoo/POS."])
    else:
        rc, out = sc(["config", SERVICE_NAME, "binPath=", bin_path, "start=", "auto", "DisplayName=", DISPLAY_NAME])
        if rc != 0:
            return False, out

    ok_rec, out_rec = configure_service_recovery()
    if not ok_rec:
        log_fn("WARN: No se pudo configurar recovery:\n" + out_rec)

    return True, out


def start_service() -> Tuple[bool, str]:
    rc, out = sc(["start", SERVICE_NAME])
    return rc == 0, out


def stop_service() -> Tuple[bool, str]:
    rc, out = sc(["stop", SERVICE_NAME])
    return rc == 0, out


def delete_service() -> Tuple[bool, str]:
    rc, out = sc(["delete", SERVICE_NAME])
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
            printers = [p[2] for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL)]
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


async def ws_handler(websocket, logger: logging.Logger):
    import websockets  # type: ignore

    logger.info("Cliente conectado: %s", getattr(websocket, "remote_address", None))

    try:
        async for msg in websocket:
            try:
                data = json.loads(msg)
            except json.JSONDecodeError:
                await websocket.send(json.dumps({"status": "error", "message": "JSON inválido"}))
                continue

            cmd = data.get("command")
            if cmd not in WEBSOCKET_COMMANDS:
                await websocket.send(json.dumps({"status": "error", "message": f"Comando inválido: {cmd}"}))
                continue

            if cmd == "health":
                resp = {"status": "success", "message": "Agent online"}
                await websocket.send(json.dumps(resp))
                continue

            if cmd == "list_printers":
                resp = list_system_printers(logger)
                await websocket.send(json.dumps(resp))
                continue

            if cmd == "print_receipt":
                printer_name = data.get("printer_name")
                raw_data = data.get("data")

                if not printer_name or not raw_data:
                    await websocket.send(json.dumps({"status": "error", "message": "Falta printer_name o data"}))
                    continue

                if platform.system() == "Windows":
                    resp = print_receipt_windows_raw(printer_name, raw_data, logger)
                else:
                    resp = {"status": "error", "message": "print_receipt solo implementado RAW en Windows por ahora"}

                await websocket.send(json.dumps(resp))
                continue

    except websockets.exceptions.ConnectionClosed:
        logger.info("Cliente desconectado")
    except Exception as exc:
        logger.exception("Error en handler: %s", exc)


async def start_agent(host: str, port: int, logger: logging.Logger):
    import websockets  # type: ignore

    if not is_port_available(host, port):
        logger.error("Puerto ocupado %s:%s. No se puede iniciar.", host, port)
        raise OSError(f"Port busy: {host}:{port}")

    async with websockets.serve(lambda ws: ws_handler(ws, logger), host, port, ping_interval=30, ping_timeout=10):
        logger.info("WebSocket escuchando en ws://%s:%s", host, port)
        await asyncio.Future()


def run_agent_service(host: str, port: int):
    app_dir = safe_app_dir()
    logger = configure_agent_logging(app_dir, "INFO")

    ok, details = ensure_dependencies(logger.info)
    if not ok:
        logger.error("Dependencias no instaladas:\n%s", details)
        raise SystemExit(2)

    try:
        asyncio.run(start_agent(host, port, logger))
    except Exception as exc:
        logger.exception("Agent crashed: %s", exc)
        raise


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
    def __init__(self):
        super().__init__()
        self.paths = gui_paths()

        self.title("LocalPrinterAgent - Service Control")
        self.geometry("980x680")
        self.resizable(True, True)

        try:
            if os.path.exists(self.paths.icon):
                self.iconbitmap(self.paths.icon)
        except Exception:
            pass

        self.host_var = tk.StringVar(value=DEFAULT_HOST)
        self.port_var = tk.StringVar(value=str(DEFAULT_PORT))

        self.dep_var = tk.StringVar(value="Dependencias: ...")
        self.admin_var = tk.StringVar(value="Permisos: ...")
        self.status_var = tk.StringVar(value="Estado servicio: ...")
        self.binpath_var = tk.StringVar(value="BinPath: ...")

        self._build_ui()
        self.log("GUI iniciado.")
        self.refresh_all()

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
        messagebox.showwarning(
            "Permisos requeridos",
            f"Para {reason} se requieren permisos de Administrador.\nSe solicitará elevación (UAC)."
        )

        ok = relaunch_as_admin()
        if not ok:
            self.log("UAC cancelado o falló.")
            messagebox.showerror("UAC", "No se pudo solicitar elevación (posiblemente cancelado).")
            return False

        self.log("UAC solicitado. Cierra esta instancia.")
        self.destroy()
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

        ttk.Label(frm, text="LocalPrinterAgent (Windows Service)", font=("Segoe UI", 15, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 10)
        )

        ttk.Label(frm, text="Host:").grid(row=1, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.host_var, width=20).grid(row=1, column=1, sticky="w", padx=(0, 10))

        ttk.Label(frm, text="Puerto:").grid(row=1, column=2, sticky="w")
        ttk.Entry(frm, textvariable=self.port_var, width=10).grid(row=1, column=3, sticky="w")

        ttk.Label(frm, textvariable=self.dep_var).grid(row=2, column=0, columnspan=4, sticky="w", pady=(8, 0))
        ttk.Label(frm, textvariable=self.admin_var).grid(row=3, column=0, columnspan=4, sticky="w")
        ttk.Label(frm, textvariable=self.status_var).grid(row=4, column=0, columnspan=4, sticky="w")
        ttk.Label(frm, textvariable=self.binpath_var, wraplength=940).grid(row=5, column=0, columnspan=4, sticky="w")

        ttk.Separator(frm).grid(row=6, column=0, columnspan=4, sticky="ew", pady=10)

        actions = ttk.Frame(frm)
        actions.grid(row=7, column=0, columnspan=4, sticky="ew")
        for i in range(6):
            actions.columnconfigure(i, weight=1)

        ttk.Button(actions, text="Instalar dependencias", command=self.on_deps).grid(row=0, column=0, padx=4, sticky="ew")
        ttk.Button(actions, text="Instalar/Actualizar servicio", command=self.on_install_service).grid(row=0, column=1, padx=4, sticky="ew")
        ttk.Button(actions, text="Abrir puerto (Firewall)", command=self.on_firewall).grid(row=0, column=2, padx=4, sticky="ew")
        ttk.Button(actions, text="Iniciar", command=self.on_start).grid(row=0, column=3, padx=4, sticky="ew")
        ttk.Button(actions, text="Detener", command=self.on_stop).grid(row=0, column=4, padx=4, sticky="ew")
        ttk.Button(actions, text="Reiniciar", command=self.on_restart).grid(row=0, column=5, padx=4, sticky="ew")

        actions2 = ttk.Frame(frm)
        actions2.grid(row=8, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        for i in range(3):
            actions2.columnconfigure(i, weight=1)

        ttk.Button(actions2, text="Eliminar servicio", command=self.on_delete).grid(row=0, column=0, padx=4, sticky="ew")
        ttk.Button(actions2, text="Refrescar", command=self.refresh_all).grid(row=0, column=1, padx=4, sticky="ew")
        ttk.Button(actions2, text="Abrir agent.log", command=self.open_agent_log).grid(row=0, column=2, padx=4, sticky="ew")

        ttk.Separator(frm).grid(row=9, column=0, columnspan=4, sticky="ew", pady=12)

        ttk.Label(frm, text="Log de interacción:", font=("Segoe UI", 10, "bold")).grid(
            row=10, column=0, columnspan=4, sticky="w"
        )

        log_frame = ttk.Frame(frm)
        log_frame.grid(row=11, column=0, columnspan=4, sticky="nsew", pady=(6, 0))
        frm.rowconfigure(11, weight=1)

        self.log_text = tk.Text(log_frame, height=18, wrap="word", state="disabled")
        scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)

        self.log_text.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        log_btns = ttk.Frame(frm)
        log_btns.grid(row=12, column=0, columnspan=4, sticky="ew", pady=10)
        log_btns.columnconfigure(0, weight=1)
        log_btns.columnconfigure(1, weight=1)

        ttk.Button(log_btns, text="Limpiar log", command=self.clear_log).grid(row=0, column=0, padx=4, sticky="ew")
        ttk.Button(log_btns, text="Abrir carpeta", command=self.open_folder).grid(row=0, column=1, padx=4, sticky="ew")

    def refresh_all(self):
        self.admin_var.set("Permisos: Administrador (OK)" if is_admin() else "Permisos: Usuario estándar (UAC requerido)")
        missing = [(pkg, mod) for pkg, mod in REQUIRED_PACKAGES if not module_exists(mod)]
        self.dep_var.set("Dependencias: OK" if not missing else "Dependencias: FALTAN -> " + ", ".join([m[0] for m in missing]))

        st = service_state()
        self.status_var.set(f"Estado servicio: {st}")
        self.binpath_var.set("BinPath: " + (get_service_binpath() or "(no disponible)" if st != "NOT_INSTALLED" else "(servicio no instalado)"))

        self.log(f"Refrescar -> servicio={st}")

    def on_deps(self):
        ok, details = ensure_dependencies(self.log)
        if ok:
            messagebox.showinfo("Dependencias", "Dependencias instaladas/verificadas correctamente.")
        else:
            messagebox.showerror("Dependencias", "No se pudieron instalar.\n\n" + details)
        self.refresh_all()

    def on_install_service(self):
        if not self.require_admin_or_relaunch("instalar/actualizar el servicio"):
            return

        try:
            host, port = self.parse_host_port()
        except ValueError as exc:
            messagebox.showerror("Configuración", str(exc))
            self.log(f"ERROR: {exc}")
            return

        ok, details = ensure_dependencies(self.log)
        if not ok:
            messagebox.showerror("Dependencias", "No se pudieron instalar.\n\n" + details)
            self.refresh_all()
            return

        ok2, out = install_or_update_service(host, port, self.log)
        self.log(out)
        if ok2:
            messagebox.showinfo("Servicio", "Servicio instalado/actualizado correctamente.")
        else:
            messagebox.showerror("Servicio", "No se pudo instalar/actualizar.\n\n" + out)
        self.refresh_all()

    def on_start(self):
        if not self.require_admin_or_relaunch("iniciar el servicio"):
            return
        ok, out = start_service()
        self.log(out)
        if ok:
            messagebox.showinfo("Servicio", "Servicio iniciado.")
        else:
            messagebox.showerror("Servicio", "No se pudo iniciar.\n\n" + out)
        self.refresh_all()

    def on_stop(self):
        if not self.require_admin_or_relaunch("detener el servicio"):
            return
        ok, out = stop_service()
        self.log(out)
        if ok:
            messagebox.showinfo("Servicio", "Servicio detenido.")
        else:
            messagebox.showerror("Servicio", "No se pudo detener.\n\n" + out)
        self.refresh_all()

    def on_restart(self):
        if not self.require_admin_or_relaunch("reiniciar el servicio"):
            return
        stop_service()
        ok, out = start_service()
        self.log(out)
        if ok:
            messagebox.showinfo("Servicio", "Servicio reiniciado.")
        else:
            messagebox.showerror("Servicio", "No se pudo reiniciar.\n\n" + out)
        self.refresh_all()

    def on_delete(self):
        if not self.require_admin_or_relaunch("eliminar el servicio"):
            return
        if service_state() == "RUNNING":
            stop_service()
        ok, out = delete_service()
        self.log(out)
        if ok:
            messagebox.showinfo("Servicio", "Servicio eliminado.")
        else:
            messagebox.showerror("Servicio", "No se pudo eliminar.\n\n" + out)
        self.refresh_all()

    def on_firewall(self):
        if not self.require_admin_or_relaunch("abrir puerto en Firewall"):
            return
        try:
            _host, port = self.parse_host_port()
        except ValueError as exc:
            messagebox.showerror("Configuración", str(exc))
            self.log(f"ERROR: {exc}")
            return
        ok, out = open_firewall_port(port)
        self.log(out)
        if ok:
            messagebox.showinfo("Firewall", f"Puerto {port} permitido (Inbound TCP).")
        else:
            messagebox.showerror("Firewall", "No se pudo crear regla.\n\n" + out)
        self.refresh_all()

    def open_agent_log(self):
        path = os.path.join(safe_app_dir(), AGENT_LOG_FILE)
        if not os.path.exists(path):
            messagebox.showinfo("agent.log", f"No existe: {path}")
            return
        try:
            os.startfile(path)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def open_folder(self):
        try:
            os.startfile(safe_app_dir())
        except Exception:
            pass


# =========================================================
# ARGUMENTS / MAIN
# =========================================================

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="LocalPrinterAgent (GUI + Windows Service in one file)")
    p.add_argument("--service", action="store_true", help="Run as service mode (no GUI)")
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    return p.parse_args()


def main() -> None:
    if not is_windows():
        messagebox.showerror("Windows requerido", "Este programa está diseñado para Windows.")
        raise SystemExit(1)

    args = parse_args()

    # Service mode
    if args.service:
        run_agent_service(args.host, args.port)
        return

    # GUI mode
    app = AgentGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
