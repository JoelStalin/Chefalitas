
import argparse
import argparse
import asyncio
import json
import logging
import platform
import shutil
import socket
import subprocess
from importlib import import_module, util

import websockets

LOG = logging.getLogger("local_printer_agent")

WEB_SOCKET_COMMANDS = {
    "list_printers",
    "print_receipt",
    "health",
}


def configure_logging(log_level: str = "INFO", log_file: str = "agent.log") -> None:
    """Configure basic file + console logging for the agent."""

    log_format = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    handlers = [logging.StreamHandler(), logging.FileHandler(log_file, encoding="utf-8")]

    logging.basicConfig(level=log_level.upper(), format=log_format, handlers=handlers)


def _port_number(value: str) -> int:
    port = int(value)
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("Port must be between 1 and 65535")
    return port


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local WebSocket printing agent")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind the WebSocket server")
    parser.add_argument("--port", type=_port_number, default=9089, help="Port for the WebSocket server")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging verbosity",
    )
    parser.add_argument(
        "--log-file",
        default="agent.log",
        help="Path to the log file",
    )
    return parser.parse_args()


def is_port_available(host: str, port: int) -> bool:
    target_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return sock.connect_ex((target_host, port)) != 0


def _load_win32print():
    """Load win32print only when available to avoid import errors on non-Windows hosts."""

    win32print_spec = util.find_spec("win32print")
    if win32print_spec is None:
        return None
    return import_module("win32print")


# --- WebSocket Server Logic ---

async def handle_connection(websocket, _path=None):
    """Handle a WebSocket connection, processing commands from the client."""

    LOG.info("Client connected from %s", websocket.remote_address)
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                command = data.get("command")

                if command == "list_printers":
                    response = list_system_printers()
                elif command == "print_receipt":
                    response = print_receipt(data)
                elif command == "health":
                    response = {"status": "success", "message": "Agent online"}
                else:
                    response = {
                        "status": "error",
                        "message": f"Unknown command. Allowed commands: {sorted(WEB_SOCKET_COMMANDS)}",
                    }

                await websocket.send(json.dumps(response))

            except json.JSONDecodeError:
                await websocket.send(json.dumps({"status": "error", "message": "Invalid JSON received."}))
            except Exception as exc:  # pylint: disable=broad-except
                error_msg = f"Unexpected error: {exc}"
                LOG.exception(error_msg)
                await websocket.send(json.dumps({"status": "error", "message": error_msg}))

    except websockets.exceptions.ConnectionClosed as exc:
        LOG.info("Connection closed: %s", exc)
    except Exception as exc:  # pylint: disable=broad-except
        LOG.exception("Server error while handling connection: %s", exc)

# --- Printer-related Functions ---

def list_system_printers():
    """Detect the operating system and return installed printers."""

    system = platform.system()

    try:
        if system == "Windows":
            win32print = _load_win32print()
            if win32print is None:
                return {
                    "status": "error",
                    "message": "win32print is required on Windows. Please install pywin32.",
                }
            printers = [printer[2] for printer in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL)]
        elif system == "Linux":
            if shutil.which("lpstat") is None:
                return {"status": "error", "message": "lpstat command not available."}
            lpstat_output = subprocess.check_output(["lpstat", "-p", "-d"], text=True, timeout=10)
            printers = [line.split(" ")[1] for line in lpstat_output.splitlines() if line.startswith("printer ")]
        else:
            return {"status": "error", "message": f"Unsupported OS: {system}"}
    except subprocess.SubprocessError as exc:
        LOG.exception("Failed to query printers: %s", exc)
        return {"status": "error", "message": f"Failed to query printers: {exc}"}
    except Exception as exc:  # pylint: disable=broad-except
        LOG.exception("Unexpected failure while listing printers: %s", exc)
        return {"status": "error", "message": f"Unexpected error: {exc}"}

    LOG.info("Printers found: %s", printers)
    return {"status": "success", "printers": printers}


def print_receipt(data):
    """Send data to a specified printer (simulated by default)."""

    printer_name = data.get("printer_name")
    receipt_data = data.get("data")

    if not printer_name or not receipt_data:
        return {"status": "error", "message": "Missing 'printer_name' or 'data'."}

    LOG.info("Simulating print to '%s'", printer_name)
    LOG.debug("Receipt payload: %s", receipt_data)

    # --- REAL PRINTING LOGIC (EXAMPLE FOR WINDOWS) ---
    # win32print = _load_win32print()
    # if win32print is None:
    #     return {"status": "error", "message": "win32print is required to send jobs."}
    # try:
    #     hPrinter = win32print.OpenPrinter(printer_name)
    #     try:
    #         hJob = win32print.StartDocPrinter(hPrinter, 1, ("Odoo Receipt", None, "RAW"))
    #         try:
    #             win32print.StartPagePrinter(hPrinter)
    #             win32print.WritePrinter(hPrinter, receipt_data.encode("utf-8"))
    #             win32print.EndPagePrinter(hPrinter)
    #         finally:
    #             win32print.EndDocPrinter(hPrinter)
    #     finally:
    #         win32print.ClosePrinter(hPrinter)
    #     return {"status": "success", "message": "Print job sent successfully."}
    # except Exception as exc:  # pylint: disable=broad-except
    #     LOG.exception("Printing failed: %s", exc)
    #     return {"status": "error", "message": f"Printing failed: {exc}"}
    # ----------------------------------------------------

    return {"status": "success", "message": "Receipt printed (simulated)."}


# --- Main Execution ---

async def start_server(host: str, port: int, stop_event: asyncio.Event) -> None:
    """Start the WebSocket server and keep it running until stop_event is set."""

    async with websockets.serve(handle_connection, host, port, ping_interval=30, ping_timeout=10):
        LOG.info("WebSocket server started at ws://%s:%s", host, port)
        await stop_event.wait()


def main():
    args = parse_args()
    configure_logging(args.log_level, args.log_file)

    if not is_port_available(args.host, args.port):
        message = (
            f"Port {args.port} on {args.host} is already in use. "
            "If another service is listening, stop it or choose a different port (e.g., 9090)."
        )
        LOG.error(message)
        raise SystemExit(1)

    stop_event = asyncio.Event()

    try:
        asyncio.run(start_server(args.host, args.port, stop_event))
    except OSError as exc:
        if exc.errno in (98, 10048):
            LOG.error("Port %s is busy or cannot be bound: %s", args.port, exc)
        else:
            LOG.exception("Failed to start server: %s", exc)
        raise SystemExit(1) from exc
    except KeyboardInterrupt:
        LOG.info("Shutdown requested by user")


if __name__ == "__main__":
    main()
