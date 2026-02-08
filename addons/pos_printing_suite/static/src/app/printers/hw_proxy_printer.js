/** @odoo-module **/

import { BasePrinter } from "@point_of_sale/app/printer/base_printer";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { ensureImagePayload } from "./image_utils";

const DEFAULT_TIMEOUT_MS = 5000;

function summarizePayload(action, receipt, printerName) {
    return {
        action,
        printer_name: printerName || undefined,
        receipt_size: receipt ? String(receipt).length : 0,
    };
}

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

function looksLikeBase64Pdf(data) {
    if (typeof data !== "string") return false;
    const trimmed = data.trim();
    if (!trimmed) return false;
    if (trimmed.startsWith("data:application/pdf;base64,")) return true;
    return trimmed.startsWith("JVBERi0");
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
        try {
            const result = await this.sendPrintingJob(receipt);
            return { successful: true, result };
        } catch (err) {
            return {
                successful: false,
                message: {
                    title: _t("Printing failed"),
                    body: err?.message || _t("HW Proxy print failed."),
                },
            };
        }
    }

    async sendPrintingJob(receipt) {
        if (!this.hwProxyBaseUrl) {
            throw new Error(_t("HW Proxy: no base URL configured."));
        }
        if (looksLikeBase64Pdf(receipt) || receipt?.type === "application/pdf") {
            throw new Error(
                _t("HW Proxy does not support PDF receipts. Use Local Agent for invoices.")
            );
        }
        const url = `${this.hwProxyBaseUrl.replace(/\/$/, "")}/hw_proxy/default_printer_action`;
        const summary = summarizePayload("print_receipt", receipt, this.printerName);
        if (odoo.debug) {
            console.debug("[pos_printing_suite] HW proxy URL:", url);
            console.debug("[pos_printing_suite] HW proxy payload summary:", summary);
        }
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
            console.error("[pos_printing_suite] HW proxy request failed", {
                url,
                payload_summary: summary,
                error_message: err?.message,
                error_stack: err?.stack,
                error_name: err?.name,
                error_code: err?.code,
                error_subtype: err?.subType,
                error_data: err?.data,
                response_body: err?.data?.message || err?.data?.debug,
            });
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
        if (odoo.debug) {
            console.debug("[pos_printing_suite] HW proxy URL:", url);
            console.debug("[pos_printing_suite] HW proxy payload summary:", {
                action: "cashbox",
                printer_name: this.printerName || undefined,
            });
        }
        return rpcWithTimeout(
            url,
            { data: { action: "cashbox", printer_name: this.printerName || undefined } },
            this.timeoutMs
        );
    }
}
