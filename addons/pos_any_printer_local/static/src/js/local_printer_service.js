
/** @odoo-module **/

import { registry } from "@web/core/registry";
import { reactive } from "@odoo/owl";

const localPrinterService = {
    dependencies: [],
    start(env) {
        const state = reactive({
            isConnected: false,
        });

        let socket;
        const socketUrl = "ws://localhost:8080";

        const connect = () => {
            console.log("LocalPrinter: Attempting to connect...");
            socket = new WebSocket(socketUrl);

            socket.onopen = () => {
                console.log("LocalPrinter: WebSocket connection established.");
                state.isConnected = true;
            };

            socket.onclose = (event) => {
                console.log("LocalPrinter: WebSocket connection closed.", event);
                state.isConnected = false;
                // Automatic reconnection attempt after 5 seconds
                setTimeout(connect, 5000);
            };

            socket.onerror = (error) => {
                console.error("LocalPrinter: WebSocket error:", error);
                state.isConnected = false;
                // Ensure the socket is closed before retrying
                socket.close();
            };

            socket.onmessage = (event) => {
                try {
                    const response = JSON.parse(event.data);
                    console.log("LocalPrinter: Message from agent:", response);
                    // You can add logic here to handle specific responses,
                    // for example, updating a list of printers.
                } catch (e) {
                    console.error("LocalPrinter: Failed to parse message:", event.data, e);
                }
            };
        };

        // Initial connection attempt
        connect();

        const _send = (payload) => {
            if (!state.isConnected) {
                console.error("LocalPrinter: Cannot send message, not connected.");
                return Promise.reject("Not Connected");
            }
            const jsonPayload = JSON.stringify(payload);
            socket.send(jsonPayload);
            return Promise.resolve();
        };

        return {
            state,

            printReceipt(printerName, data) {
                return _send({
                    command: "print_receipt",
                    printer_name: printerName,
                    data: data,
                });
            },

            getPrinters() {
                return _send({
                    command: "list_printers",
                });
            },
        };
    },
};

registry.category("services").add("local_printer_service", localPrinterService);
