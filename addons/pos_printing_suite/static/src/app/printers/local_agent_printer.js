/** @odoo-module **/

import { BasePrinter } from "@point_of_sale/app/printer/base_printer";
import { _t } from "@web/core/l10n/translation";
import { ensureImagePayload } from "./image_utils";

const LOCAL_AGENT_BASE_URL = "http://127.0.0.1:9060";

export class LocalAgentPrinter extends BasePrinter {
    setup(params) {
        super.setup(...arguments);
        this.baseUrl = params.baseUrl || LOCAL_AGENT_BASE_URL;
        this.token = params.token || "";
        this.printerName = params.printerName || "";
    }

    async sendPrintingJob(receiptB64) {
        const payload = await ensureImagePayload(this.env, receiptB64);
        if (!payload) {
            throw new Error(_t("Local Agent: empty receipt payload."));
        }
        const headers = { "Content-Type": "application/json" };
        if (this.token) {
            headers["Authorization"] = `Bearer ${this.token}`;
        }
        const res = await fetch(`${this.baseUrl}/print`, {
            method: "POST",
            headers,
            body: JSON.stringify({
                type: "image",
                printer: this.printerName,
                data: payload,
            }),
        });
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
