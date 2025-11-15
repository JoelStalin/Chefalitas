/** @odoo-module **/

import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";

patch(ReceiptScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.localPrinterService = useService("localPrinterService");
    },

    async printReceipt() {
        if (this.pos.config.enable_local_printing) {
            const receipt = this.getReceiptEnv().receipt;
            this.localPrinterService.printReceipt(receipt, this.pos.config.local_printer_name);
        } else {
            return super.printReceipt(...arguments);
        }
    },
});
