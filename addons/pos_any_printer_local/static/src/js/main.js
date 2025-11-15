/** @odoo-module **/

import { registry } from "@web/core/registry";
import { localPrinterService } from "./local_printer_service";

registry.category("services").add("localPrinterService", localPrinterService);
