/** @odoo-module **/

import { BasePrinter } from "@point_of_sale/app/printer/base_printer";
import { _t } from "@web/core/l10n/translation";

/**
 * HW Proxy / Any Printer: uses RPC or HTTP to a proxy (e.g. /hw_proxy/default_printer_action).
 * Compatible with existing "any printer" approach.
 */
export class HwProxyPrinter extends BasePrinter {
    setup(params) {
        super.setup(...arguments);
        this.hwProxyBaseUrl = params.hwProxyBaseUrl || "";
        this.printerName = params.printerName || "";
    }

    async sendPrintingJob(receiptB64) {
        if (!this.hwProxyBaseUrl) {
            throw new Error(_t("HW Proxy: no base URL configured."));
        }
        const url = `${this.hwProxyBaseUrl.replace(/\/$/, "")}/hw_proxy/default_printer_action`;
        const res = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ data: receiptB64, printer: this.printerName }),
        });
        if (!res.ok) {
            const text = await res.text();
            throw new Error(_t("HW Proxy print failed: %s", text || res.status));
        }
        return await res.json().catch(() => ({}));
    }
}
