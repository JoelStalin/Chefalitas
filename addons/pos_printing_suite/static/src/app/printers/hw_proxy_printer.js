/** @odoo-module **/

import { BasePrinter } from "@point_of_sale/app/printer/base_printer";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { ensureImagePayload } from "./image_utils";

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

    async printReceipt(receipt) {
        const payload = await ensureImagePayload(this.env, receipt);
        return this.sendPrintingJob(payload);
    }

    async sendPrintingJob(receiptB64) {
        if (!this.hwProxyBaseUrl) {
            throw new Error(_t("HW Proxy: no base URL configured."));
        }
        const url = `${this.hwProxyBaseUrl.replace(/\/$/, "")}/hw_proxy/default_printer_action`;
        try {
            const payload = await ensureImagePayload(this.env, receiptB64);
            if (!payload) {
                throw new Error(_t("HW Proxy: empty receipt payload."));
            }
            return await rpc(url, {
                data: {
                    action: "print_receipt",
                    printer_name: this.printerName || undefined,
                    receipt: payload,
                },
            });
        } catch (e) {
            throw new Error(_t("HW Proxy print failed."));
        }
    }

    openCashbox() {
        if (!this.hwProxyBaseUrl) {
            return false;
        }
        const url = `${this.hwProxyBaseUrl.replace(/\/$/, "")}/hw_proxy/default_printer_action`;
        return rpc(url, { data: { action: "cashbox", printer_name: this.printerName || undefined } });
    }
}
