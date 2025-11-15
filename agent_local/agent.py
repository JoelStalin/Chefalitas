
import asyncio
import websockets
import json
import platform
import win32print
import subprocess

# --- WebSocket Server Logic ---

async def handle_connection(websocket, path):
    """
    Handles a WebSocket connection, processing commands from the client.
    """
    print("Client connected.")
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                command = data.get("command")

                if command == "list_printers":
                    response = list_system_printers()
                elif command == "print_receipt":
                    response = print_receipt(data)
                else:
                    response = {"status": "error", "message": "Unknown command."}

                await websocket.send(json.dumps(response))

            except json.JSONDecodeError:
                await websocket.send(json.dumps({"status": "error", "message": "Invalid JSON received."}))
            except Exception as e:
                error_msg = f"An unexpected error occurred: {e}"
                print(error_msg)
                await websocket.send(json.dumps({"status": "error", "message": error_msg}))

    except websockets.exceptions.ConnectionClosed as e:
        print(f"Connection closed: {e}")
    except Exception as e:
        print(f"A server error occurred: {e}")

# --- Printer-related Functions ---

def list_system_printers():
    """
    Detects the operating system and returns a list of installed printers.
    """
    system = platform.system()
    printers = []

    try:
        if system == "Windows":
            # Use win32print for Windows
            printers = [printer[2] for printer in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL)]
        elif system == "Linux":
            # Use lpstat for Linux/CUPS
            lpstat_output = subprocess.check_output(["lpstat", "-p", "-d"], text=True)
            for line in lpstat_output.split('\n'):
                if line.startswith('printer'):
                    printers.append(line.split(' ')[1])
        else:
            return {"status": "error", "message": f"Unsupported OS: {system}"}

        print(f"Found printers: {printers}")
        return {"status": "success", "printers": printers}

    except FileNotFoundError:
        return {"status": "error", "message": "Printing command (e.g., lpstat) not found."}
    except Exception as e:
        return {"status": "error", "message": f"Failed to list printers: {e}"}

def print_receipt(data):
    """
    Sends data to a specified printer.
    This is a simulation. For a real implementation, you would use a library
    like python-escpos or send raw data via win32print.
    """
    printer_name = data.get("printer_name")
    receipt_data = data.get("data")

    if not printer_name or not receipt_data:
        return {"status": "error", "message": "Missing 'printer_name' or 'data'."}

    print("-" * 30)
    print(f"--- SIMULATING PRINT ---")
    print(f"Target Printer: {printer_name}")
    print(f"Receipt Data:\n{receipt_data}")
    print("-" * 30)

    # --- REAL PRINTING LOGIC (EXAMPLE FOR WINDOWS) ---
    # try:
    #     hPrinter = win32print.OpenPrinter(printer_name)
    #     try:
    #         hJob = win32print.StartDocPrinter(hPrinter, 1, ("Odoo Receipt", None, "RAW"))
    #         try:
    #             win32print.StartPagePrinter(hPrinter)
    #             win32print.WritePrinter(hPrinter, receipt_data.encode('utf-8'))
    #             win32print.EndPagePrinter(hPrinter)
    #         finally:
    #             win32print.EndDocPrinter(hPrinter)
    #     finally:
    #         win32print.ClosePrinter(hPrinter)
    #     return {"status": "success", "message": "Print job sent successfully."}
    # except Exception as e:
    #     return {"status": "error", "message": f"Printing failed: {e}"}
    # ----------------------------------------------------

    return {"status": "success", "message": "Receipt printed (simulated)."}

# --- Main Execution ---

async def main():
    """
    Starts the WebSocket server.
    """
    host = "localhost"
    port = 8080
    async with websockets.serve(handle_connection, host, port):
        print(f"WebSocket server started at ws://{host}:{port}")
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server stopped by user.")
