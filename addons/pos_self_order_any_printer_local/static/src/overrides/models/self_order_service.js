/** @odoo-module **/

import { SelfOrder } from "@pos_self_order/app/self_order_service";
import { patch } from "@web/core/utils/patch";
import { LocalAgentPrinter } from "@pos_any_printer_local/static/src/app/local_agent_printer";

patch(SelfOrder.prototype, {
    async setup() {
        await super.setup(...arguments);

        // En Self-Order, el "main printer" suele manejar tickets/recibos
        const cfg = this.config || {};
        const enabled = !!cfg.enable_local_printing;
        const printerName = (cfg.local_cashier_printer_name || cfg.local_printer_name || "").trim();
        if (!enabled || !printerName) {
            return;
        }
        const url = (cfg.agent_url || "http://127.0.0.1:9060");
        this.printer.setPrinter(new LocalAgentPrinter({ url, printer_name: printerName }));
    },

    create_printer(printer) {
        if (printer && printer.printer_type === "local_agent") {
            const cfg = this.config || {};
            const url = (printer.agent_url || cfg.agent_url || "http://127.0.0.1:9060");
            return new LocalAgentPrinter({
                url,
                printer_name: printer.local_printer_name || printer.name,
            });
        }
        return super.create_printer(...arguments);
    },
});
