
/** @odoo-module **/

import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

patch(ReceiptScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.printerService = useService("local_printer_service");
        this.popup = useService("popup");
    },

    async printReceipt() {
        const isLocalPrintingEnabled = this.pos.config.enable_local_printing;

        if (isLocalPrintingEnabled) {
            if (!this.printerService.state.online) {
                await this.popup.add(ErrorPopup, {
                    title: "Error de ImpresiÃ³n",
                    body: "No se pudo conectar con el agente de impresiÃ³n local. AsegÃºrese de que estÃ© instalado y en ejecuciÃ³n.",
                });
                return;
            }

            try {
                const printerName = this.pos.config.local_printer_name;
                // Get the raw receipt data.
                // In a real scenario, you'd format this into ESC/POS commands.
                // For this example, we send a simplified text version.
                const receipt = this.pos.get_order().export_for_printing();
                const receiptText = this.formatReceiptToText(receipt);

                console.log(`Sending to local printer '${printerName}':\n`, receiptText);
                await this.printerService.printReceipt(printerName, receiptText);
                // Kitchen printing (optional)
                const kitchenPrinter = (this.pos.config.kitchen_printer_name || "").trim();
                if (kitchenPrinter && kitchenPrinter !== printerName) {
                    const kitchenText = this.formatKitchenToText(receipt);
                    console.log(`Sending to kitchen printer '${kitchenPrinter}':\n`, kitchenText);
                    await this.printerService.printReceipt(kitchenPrinter, kitchenText);
                }


            } catch (error) {
                await this.popup.add(ErrorPopup, {
                    title: "Error de ImpresiÃ³n Local",
                    body: `OcurriÃ³ un error al enviar el recibo a la impresora: ${error}`,
                });
            }
        } else {
            // Fallback to the original printing method
            return super.printReceipt(...arguments);
        }
    },

    /**
     * Helper function to format the receipt object into a simple string.
     * In a real-world application, this would be a more complex function
     * that generates a specific printer language (like ESC/POS).
     */
    formatReceiptToText(receipt) {
        let text = `${receipt.company.name}\n`;
        text += `${receipt.company.street || ''}\n\n`;
        text += `Order: ${receipt.name}\n`;
        text += `Date: ${receipt.date.localestring}\n\n`;

        receipt.orderlines.forEach(line => {
            text += `${line.product_name} (${line.quantity})`.padEnd(20);
            text += `${line.price_with_tax.toFixed(2)}\n`;
        });

        text += '\n' + 'Subtotal:'.padEnd(20) + `${receipt.subtotal.toFixed(2)}\n`;
        text += 'Tax:'.padEnd(20) + `${receipt.total_tax.toFixed(2)}\n`;
        text += 'TOTAL:'.padEnd(20) + `${receipt.total_with_tax.toFixed(2)}\n`;

        return text;
    }
});

