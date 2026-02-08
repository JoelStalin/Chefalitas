# -*- coding: utf-8 -*-
"""
Windows printing backends: RAW (ESC/POS), PDF, image.
Uses win32print when on Windows; no GUI (no Tkinter).
"""
import base64
import os
import sys
import tempfile

if sys.platform == "win32":
    import win32print
    import win32api
else:
    win32print = None
    win32api = None


def list_printers():
    """Return list of printer names available on the system."""
    if not win32print:
        return []
    try:
        return [p[2] for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)]
    except Exception:
        return []


def resolve_printer_name(requested_name):
    """Resolve a printer name (case-insensitive). Raises if not found."""
    if not requested_name:
        raise RuntimeError("Printer name is required")
    names = list_printers()
    if not names:
        raise RuntimeError("No printers available on this system")
    for name in names:
        if name.lower() == requested_name.lower():
            return name
    raise RuntimeError(f"Printer not found: {requested_name}. Available: {', '.join(names)}")


def print_raw(printer_name, data_b64):
    """Send raw bytes (e.g. ESC/POS) to the printer. data_b64 is base64-encoded."""
    if not win32print:
        raise RuntimeError("Windows only")
    raw_bytes = base64.b64decode(data_b64)
    if not raw_bytes:
        return
    try:
        h = win32print.OpenPrinter(printer_name)
        try:
            win32print.StartDocPrinter(h, 1, ("POS Raw", None, "RAW"))
            win32print.StartPagePrinter(h)
            win32print.WritePrinter(h, raw_bytes)
            win32print.EndPagePrinter(h)
            win32print.EndDocPrinter(h)
        finally:
            win32print.ClosePrinter(h)
    except Exception as e:
        raise RuntimeError(f"Print raw failed: {e}") from e


def print_pdf(printer_name, data_b64):
    """Print PDF from base64 data by saving to temp file and using default PDF handler."""
    if not win32api:
        raise RuntimeError("Windows only")
    raw = base64.b64decode(data_b64)
    fd, path = tempfile.mkstemp(suffix=".pdf")
    try:
        os.write(fd, raw)
        os.close(fd)
        fd = None
        if printer_name:
            win32api.ShellExecute(0, "printto", path, f'"{printer_name}"', ".", 0)
        else:
            win32api.ShellExecute(0, "print", path, None, ".", 0)
    except Exception as e:
        if fd is not None:
            try:
                os.close(fd)
            except Exception:
                pass
        try:
            os.unlink(path)
        except Exception:
            pass
        raise RuntimeError(f"Print PDF failed: {e}") from e


def print_image(printer_name, data_b64, width_mm=80):
    """Print image (e.g. PNG/JPEG) from base64. Uses GDI print if available."""
    if not win32print:
        raise RuntimeError("Windows only")
    raw = base64.b64decode(data_b64)
    # For image, we could use PIL to render and then GDI; for simplicity we write raw to temp and try ShellExecute print.
    ext = ".png"
    if raw[:3] == b"\xff\xd8\xff":
        ext = ".jpg"
    fd, path = tempfile.mkstemp(suffix=ext)
    try:
        os.write(fd, raw)
        os.close(fd)
        fd = None
        if printer_name:
            win32api.ShellExecute(0, "printto", path, f'"{printer_name}"', ".", 0)
        else:
            win32api.ShellExecute(0, "print", path, None, ".", 0)
    except Exception as e:
        if fd is not None:
            try:
                os.close(fd)
            except Exception:
                pass
        try:
            os.unlink(path)
        except Exception:
            pass
        raise RuntimeError(f"Print image failed: {e}") from e
