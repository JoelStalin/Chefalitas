/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
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

function isSuiteAllowed(config) {
    if (!config) return false;
    if (config.printing_mode === "odoo_default") return false;
    // If the field exists and is explicitly false, block.
    if (Object.prototype.hasOwnProperty.call(config, "printing_suite_allowed")) {
        return !!config.printing_suite_allowed;
    }
    return true;
}

function getKitchenPrinterName(config) {
    return config?.local_printer_kitchen_name || config?.local_printer_cashier_name || "";
}

function createSelfOrderPrinter(env, config) {
    if (!isSuiteAllowed(config)) {
        return null;
    }
    const printerName = getKitchenPrinterName(config);
    if (!printerName) {
        return null;
    }
    const type = config.printing_mode === "local_agent" ? "local_agent" : "hw_proxy_any_printer";
    if (type === "local_agent") {
        return new LocalAgentPrinter({
            baseUrl: getLocalAgentBaseUrl(config),
            printerName,
            role: "kitchen",
            env,
        });
    }
    const baseUrl = getHwProxyBaseUrl(config);
    return new HwProxyPrinter({
        hwProxyBaseUrl: baseUrl,
        printerName,
        role: "kitchen",
        env,
    });
}

async function applySelfOrderPatch() {
    let SelfOrder;
    try {
        ({ SelfOrder } = await import("@pos_self_order/app/self_order_service"));
    } catch (e) {
        return;
    }

    patch(SelfOrder.prototype, {
        async setup() {
            await super.setup(...arguments);
            const config = this.config;
            const printer = createSelfOrderPrinter(this.env, config);
            if (printer && this.printer?.setPrinter) {
                this.printer.setPrinter(printer);
            }
            this.kitchenPrinter = printer || this.kitchenPrinter;
        },
        create_printer(printer) {
            const created = createSelfOrderPrinter(this.env, this.config);
            if (created) return created;
            if (typeof super.create_printer === "function") {
                return super.create_printer(...arguments);
            }
            return null;
        },
    });
}

applySelfOrderPatch();
