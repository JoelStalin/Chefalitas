/** @odoo-module **/

import { BasePrinter } from "@point_of_sale/app/printer/base_printer";

/**
 * LocalAgentPrinter
 * - Envía trabajos de impresión al agente Windows vía HTTP/HTTPS.
 * - Espera `img` como base64 PNG (igual que BasePrinter / Odoo POS).
 */
export class LocalAgentPrinter extends BasePrinter {
    constructor(params) {
        super(params);
        this.url = (params.url || "http://127.0.0.1:9060").replace(/\/$/, "");
        this.printer_name = params.printer_name || "";
        this.timeoutMs = params.timeoutMs || 15000;
    }

    async sendPrintingJob(img) {
        // img suele venir como base64 (sin prefijo) o data URL (data:image/png;base64,...)
        const data = (img || "").includes("base64,") ? img.split("base64,")[1] : img;
        const payload = {
            type: "image",
            printer: this.printer_name,
            data: data,
        };
        const controller = new AbortController();
        const t = setTimeout(() => controller.abort(), this.timeoutMs);

        try {
            const res = await fetch(`${this.url}/print`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
                signal: controller.signal,
            });
            if (!res.ok) {
                throw new Error(`Agent error ${res.status}`);
            }
            return true;
        } finally {
            clearTimeout(t);
        }
    }
}
