/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { LocalAgentPrinter } from "../app/printers/local_agent_printer";
import { HwProxyPrinter } from "../app/printers/hw_proxy_printer";

if (odoo.debug) {
    console.debug("[pos_printing_suite] self_order_service_patch loaded");
}

const DEFAULT_LOCAL_AGENT_HOST = "127.0.0.1";
const DEFAULT_LOCAL_AGENT_PORT = 9060;
const DEFAULT_HW_PROXY_HOST = "127.0.0.1";
const DEFAULT_HW_PROXY_PORT = 8069;

function sanitizePort(raw) {
    if (raw === null || raw === undefined || raw === "") {
        return null;
    }
    const cleaned = String(raw).replace(/,/g, "").trim();
    if (!cleaned) return null;
    const port = Number.parseInt(cleaned, 10);
    if (Number.isNaN(port) || port < 1 || port > 65535) {
        return null;
    }
    return port;
}

function sanitizeHost(raw) {
    const host = (raw || "").trim();
    if (!host || /[\s,]/.test(host)) {
        return null;
    }
    return host;
}

function notifyInvalidConfig(env, message) {
    console.error("[pos_printing_suite] Invalid configuration:", message);
    const notification = env?.services?.notification;
    if (notification?.add) {
        notification.add(message, { type: "danger" });
    }
}

function buildBaseUrl(host, port, fallbackHost, fallbackPort) {
    const safeHost = sanitizeHost(host) || sanitizeHost(fallbackHost);
    const safePort = sanitizePort(port) ?? sanitizePort(fallbackPort);
    if (!safeHost || !safePort) {
        return null;
    }
    let url = safeHost.startsWith("http") ? safeHost : `http://${safeHost}`;
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
    if (Object.prototype.hasOwnProperty.call(config, "other_devices") && !config.other_devices) {
        return false;
    }
    // If the field exists and is explicitly false, block.
    if (Object.prototype.hasOwnProperty.call(config, "printing_suite_allowed")) {
        return !!config.printing_suite_allowed;
    }
    return true;
}

function getKitchenPrinterName(config) {
    return (
        config?.local_printer_kitchen_name ||
        config?.local_printer_cashier_name ||
        config?.name ||
        ""
    );
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
        const baseUrl = getLocalAgentBaseUrl(config);
        if (!baseUrl) {
            notifyInvalidConfig(env, _t("Local Agent host/port is invalid."));
            return null;
        }
        return new LocalAgentPrinter({
            baseUrl,
            printerName,
            role: "kitchen",
            env,
        });
    }
    const baseUrl = getHwProxyBaseUrl(config);
    if (!baseUrl) {
        notifyInvalidConfig(env, _t("HW Proxy host/port is invalid."));
        return null;
    }
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
