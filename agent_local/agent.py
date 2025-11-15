
import asyncio
import websockets
import json
import win32print
import escpos.printer

async def printer_agent(websocket, path):
    print("Agente de impresora conectado.")
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                command = data.get("command")

                if command == "list_printers":
                    printers = [printer[2] for printer in win32print.EnumPrinters(2)]
                    await websocket.send(json.dumps({"status": "ok", "printers": printers}))

                elif command == "print_receipt":
                    printer_name = data.get("printer_name")
                    receipt = data.get("receipt")

                    if not printer_name or not receipt:
                        await websocket.send(json.dumps({"status": "error", "message": "Falta el nombre de la impresora o el recibo."}))
                        continue

                    try:
                        # Aquí asumimos una impresora de red/USB genérica.
                        # La configuración puede variar dependiendo del tipo de impresora (Serial, USB, etc.).
                        # Por ejemplo, para una impresora USB, podrías necesitar idVendor y idProduct.
                        p = escpos.printer.Network("192.168.1.100") # IP de ejemplo, ajustar si es necesario

                        # O si es una impresora conectada por USB y reconocida por Windows:
                        # p = escpos.printer.Win32Raw(printer_name)

                        p.text(receipt.get("company_name", "") + "\n")
                        p.text(receipt.get("address", "") + "\n")
                        p.text("-" * 32 + "\n")

                        for line in receipt.get("orderlines", []):
                            p.text(f"{line['product_name']:.20} {line['quantity']:>5} {line['price']:>6.2f}\n")

                        p.text("-" * 32 + "\n")
                        p.set(align='right')
                        p.text(f"SUBTOTAL: {receipt.get('subtotal', 0.0):.2f}\n")
                        p.text(f"IMPUESTOS: {receipt.get('tax', 0.0):.2f}\n")
                        p.set(align='center', text_type='B')
                        p.text(f"TOTAL: {receipt.get('total', 0.0):.2f}\n\n")

                        p.cut()

                        await websocket.send(json.dumps({"status": "ok", "message": "Recibo impreso exitosamente."}))

                    except Exception as e:
                        error_message = f"Error al imprimir: {str(e)}"
                        print(error_message)
                        await websocket.send(json.dumps({"status": "error", "message": error_message}))

                else:
                    await websocket.send(json.dumps({"status": "error", "message": "Comando no reconocido."}))

            except json.JSONDecodeError:
                await websocket.send(json.dumps({"status": "error", "message": "Mensaje JSON mal formado."}))
            except Exception as e:
                error_message = f"Error inesperado: {str(e)}"
                print(error_message)
                await websocket.send(json.dumps({"status": "error", "message": error_message}))

    except websockets.exceptions.ConnectionClosed:
        print("Conexión cerrada.")
    except Exception as e:
        print(f"Error en el servidor WebSocket: {str(e)}")

async def main():
    # Escucha en localhost en el puerto 8080.
    # Esto es seguro ya que solo las aplicaciones locales (como Odoo en el TPV) pueden conectarse.
    async with websockets.serve(printer_agent, "localhost", 8080):
        print("Servidor WebSocket iniciado en ws://localhost:8080")
        await asyncio.Future()  # Mantener el servidor corriendo indefinidamente

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Servidor detenido.")
