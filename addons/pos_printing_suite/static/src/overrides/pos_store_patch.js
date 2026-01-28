/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { LocalAgentPrinter } from "../app/printers/local_agent_printer";
import { HwProxyPrinter } from "../app/printers/hw_proxy_printer";

function createPrintingSuitePrinter(store, printer) {
    const type = printer.printer_type;
    if (type === "local_agent") {
        const config = store.pos?.config;
        const token = config?.local_agent_token || null;
        if (!token) {
            console.warn("POS Printing Suite: Local Agent printer configured but no token.");
            return null;
        }
        return new LocalAgentPrinter({
            ...printer,
            baseUrl: "http://127.0.0.1:9060",
            token,
            printerName: printer.local_printer_name || printer.name || "",
        });
    }
    if (type === "hw_proxy_any_printer") {
        const config = store.pos?.config;
        const baseUrl = printer.hw_proxy_ip
            ? (printer.hw_proxy_ip.startsWith("http") ? printer.hw_proxy_ip : `http://${printer.hw_proxy_ip}`)
            : (config?.any_printer_ip
                ? (config.any_printer_ip.startsWith("http") ? config.any_printer_ip : `http://${config.any_printer_ip}`)
                : "");
        return new HwProxyPrinter({
            ...printer,
            hwProxyBaseUrl: baseUrl,
            printerName: printer.local_printer_name || printer.name || "",
        });
    }
    return null;
}

// Hook into printer creation if the store has a method that builds printer instances.
// Otherwise we rely on printer service or model extensions.
patch(PosStore.prototype, {
    _createPrinter(printer) {
        const created = createPrintingSuitePrinter(this, printer);
        if (created !== null) return created;
        if (typeof super._createPrinter === "function") {
            return super._createPrinter(...arguments);
        }
        return null;
    },
});
