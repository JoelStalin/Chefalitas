
/** @odoo-module */

import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

patch(ReceiptScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.localPrinter = useService("local_printer_service");
    },

    async printReceipt() {
        if (this.pos.config.enable_local_printing) {
            console.log("Imprimiendo en impresora local...");

            if (this.localPrinter.isConnected) {
                const receipt = this.pos.get_order().export_for_printing();
                const printerName = this.pos.config.local_printer_name;

                // Formateamos un recibo simple
                const simpleReceipt = {
                    company_name: this.pos.company.name,
                    address: this.pos.company.street || '',
                    orderlines: receipt.orderlines.map(line => ({
                        product_name: line.product_name,
                        quantity: line.quantity,
                        price: line.price_with_tax,
                    })),
                    subtotal: receipt.subtotal,
                    tax: receipt.total_tax,
                    total: receipt.total_with_tax,
                };

                this.localPrinter.printReceipt(printerName, simpleReceipt);
            } else {
                console.error("El servicio de impresión local no está conectado.");
                // Opcional: mostrar un error al usuario en la UI.
            }
        } else {
            return super.printReceipt(...arguments);
        }
    },
});
