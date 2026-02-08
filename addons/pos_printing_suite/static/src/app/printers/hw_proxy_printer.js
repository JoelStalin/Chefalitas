/** @odoo-module **/

import { BasePrinter } from "@point_of_sale/app/printer/base_printer";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { ensureImagePayload } from "./image_utils";

const DEFAULT_TIMEOUT_MS = 5000;

async function rpcWithTimeout(url, params, timeoutMs) {
    const request = rpc(url, params);
    let timer;
    const timeoutPromise = new Promise((_, reject) => {
        timer = setTimeout(() => {
            if (typeof request.abort === "function") {
                request.abort(false);
            }
            reject(new Error("timeout"));
        }, timeoutMs);
    });
    try {
        return await Promise.race([request, timeoutPromise]);
    } finally {
        clearTimeout(timer);
    }
}

/**
 * HW Proxy / Any Printer: uses RPC or HTTP to a proxy (e.g. /hw_proxy/default_printer_action).
 * Compatible with existing "any printer" approach.
 */
export class HwProxyPrinter extends BasePrinter {
    setup(params) {
        super.setup(...arguments);
        this.hwProxyBaseUrl = params.hwProxyBaseUrl || "";
        if (!this.hwProxyBaseUrl && params.ip) {
            this.hwProxyBaseUrl = params.ip.startsWith("http") ? params.ip : `http://${params.ip}`;
        }
        this.printerName = params.printerName || params.printer || "";
        this.timeoutMs = params.timeoutMs || DEFAULT_TIMEOUT_MS;
    }

    async printReceipt(receipt) {
        return this.sendPrintingJob(receipt);
    }

    async sendPrintingJob(receipt) {
        if (!this.hwProxyBaseUrl) {
            throw new Error(_t("HW Proxy: no base URL configured."));
        }
        const url = `${this.hwProxyBaseUrl.replace(/\/$/, "")}/hw_proxy/default_printer_action`;
        try {
            const payload = await ensureImagePayload(this.env, receipt);
            if (!payload) {
                throw new Error(_t("HW Proxy: empty receipt payload."));
            }
            return await rpcWithTimeout(
                url,
                {
                    data: {
                        action: "print_receipt",
                        printer_name: this.printerName || undefined,
                        receipt: payload,
                    },
                },
                this.timeoutMs
            );
        } catch (err) {
            if (err?.message === "timeout") {
                throw new Error(_t("HW Proxy print timed out."));
            }
            throw new Error(_t("HW Proxy print failed: %s", err?.message || "error"));
        }
    }

    openCashbox() {
        if (!this.hwProxyBaseUrl) {
            return false;
        }
        const url = `${this.hwProxyBaseUrl.replace(/\/$/, "")}/hw_proxy/default_printer_action`;
        return rpcWithTimeout(
            url,
            { data: { action: "cashbox", printer_name: this.printerName || undefined } },
            this.timeoutMs
        );
    }
}
