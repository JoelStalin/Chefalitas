/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";
import { LocalAgentPrinter } from "@pos_any_printer_local/static/src/app/local_agent_printer";

patch(PosStore.prototype, {
    create_printer(printer) {
        // Soporta impresoras de pedido (cocina) configuradas como pos.printer
        if (printer && printer.printer_type === "local_agent") {
            const url = (printer.agent_url || this.config.agent_url || "http://127.0.0.1:9060");
            return new LocalAgentPrinter({
                url,
                printer_name: printer.local_printer_name || printer.name,
            });
        }
        return super.create_printer(...arguments);
    },
});
