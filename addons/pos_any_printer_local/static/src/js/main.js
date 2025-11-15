
/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosGlobalState } from "point_of_sale.models";
import { localPrinterService } from "./local_printer_service";

patch(PosGlobalState.prototype, {
    async _service_local_printer(config) {
        if (config.enable_local_printing) {
            return localPrinterService;
        }
        return this._super(...arguments);
    },
});
