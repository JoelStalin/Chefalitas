# -*- coding: utf-8 -*-
"""
Windows printing backends: RAW (ESC/POS), PDF, image.
Uses win32print when on Windows; no GUI (no Tkinter).
"""
import base64
import io
import os
import sys
import tempfile

if sys.platform == "win32":
    import win32print
    import win32api
    import win32ui
    import win32con
    try:
        from PIL import Image, ImageWin
    except Exception:
        Image = None
        ImageWin = None
    fitz = None
else:
    win32print = None
    win32api = None
    win32ui = None
    win32con = None
    Image = None
    ImageWin = None
    fitz = None


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
    """Print PDF from base64 data. Prefer PyMuPDF->GDI when available."""
    if not win32api:
        raise RuntimeError("Windows only")
    raw = base64.b64decode(data_b64)
    fitz_mod = fitz
    if fitz_mod is None:
        try:
            import importlib
            fitz_mod = importlib.import_module("fitz")
        except Exception:
            fitz_mod = None
    if raw and fitz_mod and Image and ImageWin and win32print:
        gdi_error = None
        try:
            doc = fitz_mod.open(stream=raw, filetype="pdf")
            for page in doc:
                pix = page.get_pixmap(dpi=200)
                mode = "RGBA" if pix.alpha else "RGB"
                img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
                _print_pil_image_gdi(printer_name, img)
            return
        except Exception as e:
            gdi_error = e
        # fall through to ShellExecute
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
        detail = f"Print PDF failed: {e}"
        if 'gdi_error' in locals() and gdi_error:
            detail += f". GDI/PyMuPDF error: {gdi_error}"
        raise RuntimeError(detail) from e


def _print_pil_image_gdi(printer_name, img):
    if not (win32print and win32ui and win32con and Image and ImageWin):
        raise RuntimeError("Image printing requires Pillow and pywin32.")
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")
    hdc = win32ui.CreateDC()
    try:
        hdc.CreatePrinterDC(printer_name)
        printable_width = hdc.GetDeviceCaps(win32con.HORZRES)
        printable_height = hdc.GetDeviceCaps(win32con.VERTRES)
        scale = min(printable_width / img.width, printable_height / img.height)
        target_w = max(1, int(img.width * scale))
        target_h = max(1, int(img.height * scale))
        hdc.StartDoc("POS Image")
        hdc.StartPage()
        dib = ImageWin.Dib(img)
        dib.draw(hdc.GetHandleOutput(), (0, 0, target_w, target_h))
        hdc.EndPage()
        hdc.EndDoc()
    finally:
        try:
            hdc.DeleteDC()
        except Exception:
            pass


def _print_image_gdi(printer_name, raw):
    if not (win32print and win32ui and win32con and Image and ImageWin):
        raise RuntimeError("Image printing requires Pillow and pywin32.")
    img = Image.open(io.BytesIO(raw))
    _print_pil_image_gdi(printer_name, img)


def print_image(printer_name, data_b64, width_mm=80):
    """Print image (e.g. PNG/JPEG) from base64. Uses GDI print when possible."""
    if not win32print:
        raise RuntimeError("Windows only")
    raw = base64.b64decode(data_b64)
    if not raw:
        return
    gdi_error = None
    try:
        _print_image_gdi(printer_name, raw)
        return
    except Exception as e:
        gdi_error = e
    # Fallback: write to temp and try ShellExecute print (may require GUI handler).
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
        raise RuntimeError(f"Print image failed: {e}. GDI error: {gdi_error}") from e
