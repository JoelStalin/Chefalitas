import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";
import { AnyPrinter } from "../../app/epson_printer";


patch(PosStore.prototype, {
    afterProcessServerData() {

        var self = this;
        return super.afterProcessServerData(...arguments).then(function () {
            if (self.config.other_devices && self.config.any_printer_ip) {
                self.hardwareProxy.printer = new AnyPrinter({ ip: self.config.any_printer_ip, printer: self.config.name});
            }
        });
    },
    create_printer(config) {
        if (config.printer_type === "any_printer") {
            return new AnyPrinter({ ip: config.any_printer_ip, printer: config.name});
        } else {
            return super.create_printer(...arguments);
        }
    },
});
