
/** @odoo-module */

import { registry } from "@web/core/registry";
import { EventBus } from "@odoo/owl";

export const localPrinterService = {
    dependencies: ["rpc"],
    start(env, { rpc }) {
        const bus = new EventBus();
        let socket = null;

        function connect() {
            console.log("Intentando conectar al agente de impresión local...");
            socket = new WebSocket("ws://localhost:8080");

            socket.onopen = () => {
                console.log("Conexión con el agente de impresión establecida.");
                bus.trigger("status-changed", { status: "connected" });
            };

            socket.onclose = () => {
                console.log("Conexión con el agente de impresión perdida. Reintentando en 5 segundos...");
                bus.trigger("status-changed", { status: "disconnected" });
                setTimeout(connect, 5000);
            };

            socket.onerror = (error) => {
                console.error("Error en la conexión WebSocket:", error);
                bus.trigger("status-changed", { status: "error" });
                socket.close();
            };

            socket.onmessage = (event) => {
                const response = JSON.parse(event.data);
                if (response.status === 'ok') {
                    console.log('Respuesta del agente:', response);
                } else {
                    console.error('Error del agente:', response.message);
                }
            };
        }

        connect();

        return {
            bus,
            get isConnected() {
                return socket && socket.readyState === WebSocket.OPEN;
            },

            listPrinters() {
                if (!this.isConnected) {
                    console.error("No se pueden listar las impresoras. El agente no está conectado.");
                    return;
                }
                socket.send(JSON.stringify({ command: "list_printers" }));
            },

            printReceipt(printerName, receipt) {
                if (!this.isConnected) {
                    console.error("No se puede imprimir. El agente no está conectado.");
                    return;
                }
                const payload = {
                    command: "print_receipt",
                    printer_name: printerName,
                    receipt: receipt,
                };
                socket.send(JSON.stringify(payload));
            },
        };
    },
};

registry.category("services").add("local_printer_service", localPrinterService);
