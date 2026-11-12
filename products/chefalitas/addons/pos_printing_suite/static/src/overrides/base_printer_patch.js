/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { BasePrinter } from "@point_of_sale/app/printer/base_printer";
import { toCanvas } from "@point_of_sale/app/utils/html-to-image";

const RENDER_OPTIONS = {
    backgroundColor: "#ffffff",
    pixelRatio: 1,
    skipFonts: true,
    fontEmbedCSS: "",
    cacheBust: true,
};

function toHTMLElement(receipt) {
    if (!receipt) return null;
    if (receipt instanceof HTMLElement) return receipt;
    if (receipt?.el instanceof HTMLElement) return receipt.el;
    if (typeof receipt === "string") {
        const wrapper = document.createElement("div");
        wrapper.innerHTML = receipt;
        return wrapper;
    }
    return null;
}

async function safeHtmlToCanvas(receipt) {
    const element = toHTMLElement(receipt);
    if (!element) {
        throw new Error(_t("Unable to render receipt."));
    }
    const container = document.querySelector(".render-container") || document.body;
    const clone = element.cloneNode(true);
    if (clone.classList) {
        clone.classList.add("pos-receipt-print");
    }
    container.appendChild(clone);
    try {
        const width = Math.ceil(
            clone.scrollWidth || clone.clientWidth || element.scrollWidth || element.clientWidth || 0
        );
        const height = Math.ceil(
            clone.scrollHeight || clone.clientHeight || element.scrollHeight || element.clientHeight || 0
        );
        if (width) {
            clone.style.width = `${width}px`;
        }
        if (height) {
            clone.style.height = `${height}px`;
        }
        await new Promise((resolve) => requestAnimationFrame(resolve));
        return await toCanvas(clone, {
            ...RENDER_OPTIONS,
            height: height || undefined,
            width: width || undefined,
        });
    } finally {
        clone.remove();
    }
}

patch(BasePrinter.prototype, {
    async printReceipt(receipt) {
        if (!this.isPrintingSuitePrinter && typeof super.printReceipt === "function") {
            return super.printReceipt(...arguments);
        }
        if (receipt) {
            this.receiptQueue.push(receipt);
        }
        let image, printResult;
        while (this.receiptQueue.length > 0) {
            receipt = this.receiptQueue.shift();
            try {
                const canvas = await safeHtmlToCanvas(receipt);
                image = this.processCanvas(canvas);
            } catch (err) {
                this.receiptQueue.length = 0;
                return {
                    successful: false,
                    message: {
                        title: _t("Printing failed"),
                        body: err?.message || _t("Unable to render receipt."),
                    },
                };
            }
            try {
                printResult = await this.sendPrintingJob(image);
            } catch {
                this.receiptQueue.length = 0;
                return this.getActionError();
            }
            if (!printResult || printResult.result === false) {
                this.receiptQueue.length = 0;
                return this.getResultsError(printResult);
            }
        }
        return { successful: true };
    },
});
