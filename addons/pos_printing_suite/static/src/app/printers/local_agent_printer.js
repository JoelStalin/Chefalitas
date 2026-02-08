/** @odoo-module **/

import { BasePrinter } from "@point_of_sale/app/printer/base_printer";
import { _t } from "@web/core/l10n/translation";
import { ensureImagePayload } from "./image_utils";

const LOCAL_AGENT_BASE_URL = "http://127.0.0.1:9060";
const DEFAULT_TIMEOUT_MS = 5000;

export class LocalAgentPrinter extends BasePrinter {
    setup(params) {
        super.setup(...arguments);
        this.baseUrl = params.baseUrl || LOCAL_AGENT_BASE_URL;
        this.token = params.token || "";
        this.printerName = params.printerName || params.printer || "";
        this.timeoutMs = params.timeoutMs || DEFAULT_TIMEOUT_MS;
    }

    async printReceipt(receipt) {
        return this.sendPrintingJob(receipt);
    }

    async sendPrintingJob(receipt) {
        const payload = await ensureImagePayload(this.env, receipt);
        if (!payload) {
            throw new Error(_t("Local Agent: empty receipt payload."));
        }
        const headers = { "Content-Type": "application/json" };
        if (this.token) {
            headers["Authorization"] = `Bearer ${this.token}`;
        }
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), this.timeoutMs);
        let res;
        try {
            res = await fetch(`${this.baseUrl}/print`, {
                method: "POST",
                headers,
                signal: controller.signal,
                body: JSON.stringify({
                    type: "image",
                    printer: this.printerName,
                    data: payload,
                }),
            });
        } catch (err) {
            if (err?.name === "AbortError") {
                throw new Error(_t("Local Agent print timed out."));
            }
            throw new Error(_t("Local Agent connection failed."));
        } finally {
            clearTimeout(timer);
        }
        if (!res.ok) {
            const text = await res.text();
            throw new Error(_t("Local Agent print failed: %s", text || res.status));
        }
        return await res.json();
    }

    openCashbox() {
        // Local Agent doesn't implement cashbox control; return false to avoid crash.
        return false;
    }
}
