import { rpc } from "@web/core/network/rpc";

import { BasePrinter } from "@point_of_sale/app/printer/base_printer";

/**
 * Printer that sends print requests thru /hw_proxy endpoints.
 * Doesn't require pos_iot to be installed.
 */
export class AnyPrinter extends BasePrinter {

    setup(params) {
        super.setup(...arguments);
        // console.log("_+__________________-params");
        // console.log(params);
        // debugger


        this.url = 'http://' + params.ip;
        this.address = this.url + '/hw_proxy/default_printer_action';
        this.printer_name = params.printer;
    }

    sendAction(data) {
        // debugger
        // console.log("________________ data");
        // console.log(data);
        return rpc(`${this.url}/hw_proxy/default_printer_action`,
            {
                data: {
                    action: data.action,
                    printer_name: this.printer_name,
                    receipt: data.receipt,

                }
            }
        );
    }

    /**
     * @override
     */
    openCashbox() {
        return this.sendAction({ action: "cashbox" });
    }

    /**
     * @override
     */
    sendPrintingJob(img) {
        return this.sendAction({ action: "print_receipt", receipt: img });
    }
}