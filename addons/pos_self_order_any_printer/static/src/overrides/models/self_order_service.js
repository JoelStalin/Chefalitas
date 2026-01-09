import { SelfOrder } from "@pos_self_order/app/self_order_service";
import { patch } from "@web/core/utils/patch";
import { AnyPrinter } from "@pos_any_printer/static/src/app/epson_printer";
alert("hola 1")

patch(SelfOrder.prototype, {
    async setup() {
        alert("hola 1")

        await super.setup(...arguments);
        if (!this.config.any_printer_ip || !this.config.other_devices) {
            return;
        }
        this.printer.setPrinter(
            new AnyPrinter({
                ip: this.config.any_printer_ip,
                printer_name: this.config.name 
            })
        );
    },
    create_printer(printer) {
        alert("hola 3")
        if (printer.printer_type === "any_printer") {
            return new AnyPrinter({ ip: printer.any_printer_ip, printer: printer.name });
        }
        return super.create_printer(...arguments);
    },
});
