/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { HardwareProxy } from "@point_of_sale/app/hardware_proxy/hardware_proxy_service";
import { LocalAgentPrinter } from "../app/printers/local_agent_printer";
import { HwProxyPrinter } from "../app/printers/hw_proxy_printer";

const DEFAULT_LOCAL_AGENT_HOST = "127.0.0.1";
const DEFAULT_LOCAL_AGENT_PORT = 9060;
const DEFAULT_HW_PROXY_HOST = "127.0.0.1";
const DEFAULT_HW_PROXY_PORT = 8069;

function buildBaseUrl(host, port, fallbackHost, fallbackPort) {
    const rawHost = (host || "").trim() || fallbackHost;
    const safePort = port || fallbackPort;
    let url = rawHost.startsWith("http") ? rawHost : `http://${rawHost}`;
    const hasPort = /:\d{2,5}(\/|$)/.test(url);
    if (!hasPort && safePort) {
        url = url.replace(/\/?$/, `:${safePort}`);
    }
    return url;
}

function getPosConfig(store) {
    return store?.config || store?.pos?.config || null;
}

function getPrinterName(store, printer) {
    const config = getPosConfig(store);
    const fallback = config?.name || printer?.name || "";
    if (printer?.role === "kitchen") {
        return config?.local_printer_kitchen_name || printer.local_printer_name || printer.name || fallback;
    }
    return config?.local_printer_cashier_name || printer.local_printer_name || printer.name || fallback;
}

function getLocalAgentBaseUrl(config) {
    return buildBaseUrl(
        config?.local_agent_host,
        config?.local_agent_port,
        DEFAULT_LOCAL_AGENT_HOST,
        DEFAULT_LOCAL_AGENT_PORT
    );
}

function getHwProxyBaseUrl(config) {
    return buildBaseUrl(
        config?.any_printer_ip || config?.proxy_ip,
        config?.any_printer_port,
        DEFAULT_HW_PROXY_HOST,
        DEFAULT_HW_PROXY_PORT
    );
}

function createPrintingSuitePrinter(store, printer) {
    const config = getPosConfig(store);
    if (!config?.printing_suite_allowed) {
        return null;
    }
    const printerName = getPrinterName(store, printer);
    const type =
        printer.printer_type ||
        (config.printing_mode === "local_agent" ? "local_agent" : "hw_proxy_any_printer");
    if (type === "local_agent") {
        return new LocalAgentPrinter({
            ...printer,
            baseUrl: getLocalAgentBaseUrl(config),
            printerName,
        });
    }
    if (type === "hw_proxy_any_printer") {
        const baseUrl = getHwProxyBaseUrl(config);
        if (!baseUrl) {
            return null;
        }
        return new HwProxyPrinter({
            ...printer,
            hwProxyBaseUrl: baseUrl,
            printerName,
        });
    }
    return null;
}

function setupPrintingSuitePrinters(store) {
    if (store._printingSuiteInitialized) {
        return;
    }
    const config = getPosConfig(store);
    if (!config?.printing_suite_allowed) {
        return;
    }
    const printerType =
        config.printing_mode === "local_agent" ? "local_agent" : "hw_proxy_any_printer";

    // Receipt (cashier) printer
    const receiptPrinter = createPrintingSuitePrinter(store, {
        printer_type: printerType,
        role: "cashier",
    });
    if (receiptPrinter) {
        if (store.hardwareProxy) {
            store.hardwareProxy.printer = receiptPrinter;
        }
        if (store.printer?.setPrinter) {
            store.printer.setPrinter(receiptPrinter);
        }
    }

    // Kitchen printer (single)
    if (config.local_printer_kitchen_name) {
        const kitchenPrinter = createPrintingSuitePrinter(store, {
            printer_type: printerType,
            role: "kitchen",
        });
        if (kitchenPrinter) {
            const allCategoryIds = store.models["pos.category"]
                .getAll()
                .map((c) => c.id);
            kitchenPrinter.config = { product_categories_ids: allCategoryIds };
            store.unwatched.printers = [kitchenPrinter];
            store.printers_category_ids_set = new Set(allCategoryIds);
            store.config.iface_printers = true;
        }
    }

    store._printingSuiteInitialized = true;
}

// Hook into printer creation if the store has a method that builds printer instances.
// Otherwise we rely on printer service or model extensions.
patch(PosStore.prototype, {
    async afterProcessServerData() {
        await super.afterProcessServerData(...arguments);
        setupPrintingSuitePrinters(this);
    },
    async initServerData() {
        await super.initServerData(...arguments);
        setupPrintingSuitePrinters(this);
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
});

patch(HardwareProxy.prototype, {
    connectToPrinter() {
        if (this.pos?.config?.printing_suite_allowed) {
            return;
        }
        return super.connectToPrinter(...arguments);
    },
});
