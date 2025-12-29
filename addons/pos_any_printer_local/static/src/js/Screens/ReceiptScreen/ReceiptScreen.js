/** @odoo-module **/

import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

patch(ReceiptScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.localPrinter = useService("local_printer_service");
        this.popup = useService("popup");
    },

    /**
     * Imprime el recibo en la impresora de CAJA (configurable).
     * Nota: para cocina se recomienda usar impresoras de pedido (pos.printer) con tipo 'local_agent'.
     */
    async printReceipt() {
        const config = this.pos.config || {};
        const enabled = !!config.enable_local_printing;
        const printerName = (config.local_cashier_printer_name || config.local_printer_name || "").trim();

        if (!enabled) {
            return super.printReceipt(...arguments);
        }
        if (!printerName) {
            await this.popup.add(ErrorPopup, {
                title: "Impresora no configurada",
                body: "Configura la impresora local de CAJA en la configuración del TPV.",
            });
            return;
        }
        try {
            const text = this._buildReceiptText();
            await this.localPrinter.printReceipt(printerName, text);
            await this.popup.add(ErrorPopup, {
                title: "Impresión enviada",
                body: `Se envió el recibo a: ${printerName}`,
            });
        } catch (error) {
            await this.popup.add(ErrorPopup, {
                title: "Error imprimiendo",
                body: error?.message || String(error),
            });
        }
    },

    _buildReceiptText() {
        const order = this.currentOrder;
        const r = order.export_for_printing();

        const pad = (s, n) => (String(s || "").slice(0, n)).padEnd(n, " ");
        let out = "";

        out += `${r.company?.name || ""}\n`;
        out += `${r.name || ""}\n`;
        out += `------------------------------\n`;

        for (const line of (r.orderlines || [])) {
            const name = line.product_name || "";
            const qty = line.quantity || 0;
            const price = (line.price_with_tax || 0).toFixed(2);
            out += `${pad(name, 20)}${pad(qty, 4)}${pad(price, 6)}\n`;
        }

        out += `------------------------------\n`;
        out += `${pad("Subtotal:", 20)}${(r.subtotal || 0).toFixed(2)}\n`;
        out += `${pad("Impuestos:", 20)}${(r.total_tax || 0).toFixed(2)}\n`;
        out += `${pad("TOTAL:", 20)}${(r.total_with_tax || 0).toFixed(2)}\n`;
        out += `\n\n`;

        return out;
    },
});
