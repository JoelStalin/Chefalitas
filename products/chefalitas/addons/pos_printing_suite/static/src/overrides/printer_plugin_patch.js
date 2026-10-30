import { patch } from "@web/core/utils/patch";
import { PosTicketPrinterPlugin } from "@point_of_sale/app/plugins/pos_ticket_printer_plugin";
import { LocalAgentPrinter } from "../app/printers/local_agent_printer";
import { HwProxyPrinter } from "../app/printers/hw_proxy_printer";

const DEFAULT_AGENT_HOST = "127.0.0.1";
const DEFAULT_AGENT_PORT = 9060;

/**
 * Odoo 20 builds printer instances from the pos.printer records of the config
 * (receipt_printer_ids / preparation_printer_ids). pos_printing_suite keeps those records
 * in sync with its settings (see pos.config._sync_printing_suite_printers).
 */
patch(PosTicketPrinterPlugin.prototype, {
    async createPrinterInstance(printer) {
        const config = this.config;
        if (printer.printer_type === "local_agent") {
            const host = config.local_agent_host || DEFAULT_AGENT_HOST;
            const port = config.local_agent_port || DEFAULT_AGENT_PORT;
            return new LocalAgentPrinter({
                printer,
                baseUrl: `http://${host}:${port}`,
                token: config.agent_token_pos || "",
                printerName: printer.local_printer_name || printer.name,
            });
        }
        if (printer.printer_type === "hw_proxy_any_printer") {
            return new HwProxyPrinter({
                printer,
                ip: printer.hw_proxy_ip || config.any_printer_ip,
                printerName: printer.local_printer_name || printer.name,
            });
        }
        return super.createPrinterInstance(...arguments);
    },
});
