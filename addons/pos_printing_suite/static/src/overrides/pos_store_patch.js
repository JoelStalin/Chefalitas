/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { HardwareProxy } from "@point_of_sale/app/hardware_proxy/hardware_proxy_service";
import { LocalAgentPrinter } from "../app/printers/local_agent_printer";
import { HwProxyPrinter } from "../app/printers/hw_proxy_printer";

const LOCAL_AGENT_BASE_URL = "http://127.0.0.1:9060";
const DEFAULT_HW_PROXY_URL = "http://127.0.0.1:8069";

function normalizeUrl(raw, defaultPort = "8069") {
    if (!raw) return "";
    let url = raw.startsWith("http") ? raw : `http://${raw}`;
    const hasPort = /:\d{2,5}(\/|$)/.test(url);
    if (!hasPort) {
        url = url.replace(/\/?$/, `:${defaultPort}`);
    }
    return url;
}

function getReceiptImageData(config) {
    const img = config?.receipt_image;
    if (!img) return null;
    return img.startsWith("data:image") ? img : `data:image/png;base64,${img}`;
}

function getPrinterName(store, printer) {
    const config = store.pos?.config;
    if (printer?.role === "kitchen") {
        return config?.local_printer_kitchen_name || printer.local_printer_name || printer.name || "";
    }
    return config?.local_printer_cashier_name || printer.local_printer_name || printer.name || "";
}

function getHwProxyBaseUrl(config) {
    return normalizeUrl(
        config?.any_printer_ip || config?.proxy_ip || DEFAULT_HW_PROXY_URL,
        "8069"
    );
}

function createPrintingSuitePrinter(store, printer) {
    const config = store.pos?.config;
    if (!config?.printing_suite_allowed) {
        return null;
    }
    const type =
        printer.printer_type ||
        (config.printing_mode === "local_agent" ? "local_agent" : "hw_proxy_any_printer");
    if (type === "local_agent") {
        const token = config?.local_agent_token || null;
        if (!token) {
            console.warn("POS Printing Suite: Local Agent printer configured but no token.");
            return null;
        }
        return new LocalAgentPrinter({
            ...printer,
            baseUrl: LOCAL_AGENT_BASE_URL,
            token,
            printerName: getPrinterName(store, printer),
        });
    }
    if (type === "hw_proxy_any_printer") {
        const baseUrl = getHwProxyBaseUrl(config);
        return new HwProxyPrinter({
            ...printer,
            hwProxyBaseUrl: baseUrl,
            printerName: getPrinterName(store, printer),
        });
    }
    return null;
}

// Hook into printer creation if the store has a method that builds printer instances.
// Otherwise we rely on printer service or model extensions.
patch(PosStore.prototype, {
    async initServerData() {
        await super.initServerData(...arguments);
        const config = this.config;
        if (!config?.printing_suite_allowed) {
            return;
        }
        const printerType =
            config.printing_mode === "local_agent" ? "local_agent" : "hw_proxy_any_printer";

        // Receipt (cashier) printer
        const receiptPrinter = createPrintingSuitePrinter(this, {
            printer_type: printerType,
            role: "cashier",
        });
        if (receiptPrinter) {
            if (this.hardwareProxy) {
                this.hardwareProxy.printer = receiptPrinter;
            }
            if (this.printer?.setPrinter) {
                this.printer.setPrinter(receiptPrinter);
            }
        }

        // Kitchen printer (single)
        if (config.local_printer_kitchen_name) {
            const kitchenPrinter = createPrintingSuitePrinter(this, {
                printer_type: printerType,
                role: "kitchen",
            });
            if (kitchenPrinter) {
                const allCategoryIds = this.models["pos.category"]
                    .getAll()
                    .map((c) => c.id);
                kitchenPrinter.config = { product_categories_ids: allCategoryIds };
                this.unwatched.printers = [kitchenPrinter];
                this.printers_category_ids_set = new Set(allCategoryIds);
                this.config.iface_printers = true;
            }
        }
    },
    create_printer(printer) {
        const created = createPrintingSuitePrinter(this, printer);
        if (created !== null) return created;
        if (typeof super.create_printer === "function") {
            return super.create_printer(...arguments);
        }
        return null;
    },
    _createPrinter(printer) {
        const created = createPrintingSuitePrinter(this, printer);
        if (created !== null) return created;
        if (typeof super._createPrinter === "function") {
            return super._createPrinter(...arguments);
        }
        return null;
    },
    getReceiptHeaderData(order) {
        const data = super.getReceiptHeaderData(...arguments);
        if (this.config?.printing_suite_allowed) {
            const receiptImage = getReceiptImageData(this.config);
            if (receiptImage) {
                data.receipt_image = receiptImage;
            }
        }
        return data;
    },
    getPrintingChanges(order, diningModeUpdate) {
        const changes = super.getPrintingChanges(...arguments);
        if (this.config?.printing_suite_allowed) {
            const receiptImage = getReceiptImageData(this.config);
            if (receiptImage) {
                changes.receipt_image = receiptImage;
            }
        }
        return changes;
    },
});

patch(HardwareProxy.prototype, {
    connectToPrinter() {
        if (this.pos?.config?.printing_suite_allowed) {
            return;
        }
        return super.connectToPrinter(...arguments);
    },
});
