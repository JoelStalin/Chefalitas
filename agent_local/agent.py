import asyncio
import json
import websockets
import win32print

async def handler(websocket, path):
    print(f"Client connected from {websocket.remote_address}")
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                command = data.get("command")

                if command == "list_printers":
                    printers = [printer[2] for printer in win32print.EnumPrinters(2)]
                    response = {
                        "command": "list_printers",
                        "printers": printers,
                    }
                    await websocket.send(json.dumps(response))

                elif command == "print_receipt":
                    printer_name = data.get("printer_name")
                    receipt_data = data.get("data")

                    hPrinter = win32print.OpenPrinter(printer_name)
                    try:
                        hJob = win32print.StartDocPrinter(hPrinter, 1, ("receipt", None, "RAW"))
                        try:
                            win32print.StartPagePrinter(hPrinter)
                            win32print.WritePrinter(hPrinter, receipt_data.encode())
                            win32print.EndPagePrinter(hPrinter)
                        finally:
                            win32print.EndDocPrinter(hPrinter)
                    finally:
                        win32print.ClosePrinter(hPrinter)

                    response = {"status": "success"}
                    await websocket.send(json.dumps(response))

            except Exception as e:
                print(f"Error processing message: {e}")
                response = {"status": "error", "message": str(e)}
                await websocket.send(json.dumps(response))

    except websockets.exceptions.ConnectionClosed:
        print(f"Client disconnected from {websocket.remote_address}")

async def main():
    async with websockets.serve(handler, "localhost", 8080):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
