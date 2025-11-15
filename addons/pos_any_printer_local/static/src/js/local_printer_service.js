/** @odoo-module **/

import { registry } from "@web/core/registry";
import { reactive } from "@odoo/owl";

export const localPrinterService = {
    dependencies: ["rpc"],
    async start(env, { rpc }) {
        const state = reactive({
            isConnected: false,
            printers: [],
        });

        let socket;
        const socketUrl = "ws://localhost:8080";

        const connect = () => {
            socket = new WebSocket(socketUrl);

            socket.onopen = () => {
                console.log("WebSocket connected");
                state.isConnected = true;
                getPrinters();
            };

            socket.onclose = () => {
                console.log("WebSocket disconnected, reconnecting...");
                state.isConnected = false;
                setTimeout(connect, 3000);
            };

            socket.onerror = (error) => {
                console.error("WebSocket error:", error);
                socket.close();
            };

            socket.onmessage = (event) => {
                const response = JSON.parse(event.data);
                if (response.command === "list_printers") {
                    state.printers = response.printers;
                }
            };
        };

        const getPrinters = () => {
            if (socket && socket.readyState === WebSocket.OPEN) {
                socket.send(JSON.stringify({ command: "list_printers" }));
            }
        };

        const printReceipt = (receipt, printer_name) => {
            if (socket && socket.readyState === WebSocket.OPEN) {
                socket.send(JSON.stringify({
                    command: "print_receipt",
                    printer_name: printer_name,
                    data: receipt,
                }));
            } else {
                console.error("WebSocket is not connected.");
            }
        };

        connect();

        return {
            state,
            getPrinters,
            printReceipt,
        };
    },
};
