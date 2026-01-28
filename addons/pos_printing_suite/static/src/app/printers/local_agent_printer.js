/** @odoo-module **/

import { BasePrinter } from "@point_of_sale/app/printer/base_printer";
import { _t } from "@web/core/l10n/translation";

const LOCAL_AGENT_BASE_URL = "http://127.0.0.1:9060";

export class LocalAgentPrinter extends BasePrinter {
    setup(params) {
        super.setup(...arguments);
        this.baseUrl = params.baseUrl || LOCAL_AGENT_BASE_URL;
        this.token = params.token || "";
        this.printerName = params.printerName || "";
    }

    async sendPrintingJob(receiptB64) {
        if (!this.token) {
            throw new Error(_t("Local Agent: no token configured."));
        }
        const res = await fetch(`${this.baseUrl}/print`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${this.token}`,
            },
            body: JSON.stringify({
                type: "raw",
                printer: this.printerName,
                data: receiptB64,
            }),
        });
        if (!res.ok) {
            const text = await res.text();
            throw new Error(_t("Local Agent print failed: %s", text || res.status));
        }
        return await res.json();
    }
}
