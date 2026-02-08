/** @odoo-module **/

import { BasePrinter } from "@point_of_sale/app/printer/base_printer";
import { _t } from "@web/core/l10n/translation";
import { ensureImagePayload } from "./image_utils";

const LOCAL_AGENT_BASE_URL = "http://127.0.0.1:9060";
const DEFAULT_TIMEOUT_MS = 5000;
const LOOPBACK_REGEX = /(127\.0\.0\.1|localhost|::1)/i;

function stripDataUrl(data) {
    if (typeof data !== "string") {
        return data;
    }
    const match = data.match(/^data:([a-zA-Z0-9.+-]+\/[a-zA-Z0-9.+-]+);base64,(.*)$/);
    return match ? match[2] : data;
}

function isLoopbackBlocked(err, baseUrl) {
    if (!baseUrl || !LOOPBACK_REGEX.test(baseUrl)) {
        return false;
    }
    if (!window.isSecureContext) {
        return false;
    }
    const message = (err?.message || "").toLowerCase();
    return message.includes("failed to fetch") || message.includes("networkerror");
}

function buildLoopbackHelpMessage(env) {
    const url = env?.pos?.config?.agent_policy_download_url;
    if (url) {
        return _t(
            "Chrome/Edge blocked access to the local agent. Ask an admin to download and run the loopback policy: %s",
            url
        );
    }
    return _t(
        "Chrome/Edge blocked access to the local agent. Ask an admin to enable the loopback policy for this POS domain."
    );
}

function looksLikeBase64Pdf(data) {
    if (typeof data !== "string") return false;
    const trimmed = data.trim();
    if (!trimmed) return false;
    if (trimmed.startsWith("data:application/pdf;base64,")) return true;
    return trimmed.startsWith("JVBERi0");
}

async function toBase64FromBlob(blob) {
    const buffer = await blob.arrayBuffer();
    const bytes = new Uint8Array(buffer);
    let binary = "";
    for (let i = 0; i < bytes.length; i++) {
        binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
}

async function normalizePayload(env, receipt) {
    if (!receipt) {
        throw new Error(_t("Local Agent: empty receipt payload."));
    }
    if (typeof receipt === "string") {
        if (looksLikeBase64Pdf(receipt)) {
            return { type: "pdf", data: stripDataUrl(receipt) };
        }
    }
    if (receipt?.type === "application/pdf" && typeof receipt.arrayBuffer === "function") {
        const b64 = await toBase64FromBlob(receipt);
        return { type: "pdf", data: b64 };
    }
    if (receipt?.pdf && looksLikeBase64Pdf(receipt.pdf)) {
        return { type: "pdf", data: stripDataUrl(receipt.pdf) };
    }
    const imagePayload = await ensureImagePayload(env, receipt);
    if (!imagePayload) {
        throw new Error(_t("Local Agent: empty receipt payload."));
    }
    return { type: "image", data: stripDataUrl(imagePayload) };
}

export class LocalAgentPrinter extends BasePrinter {
    setup(params) {
        super.setup(...arguments);
        this.baseUrl = params.baseUrl || LOCAL_AGENT_BASE_URL;
        this.token = params.token || "";
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
                    body: err?.message || _t("Local Agent print failed."),
                },
            };
        }
    }

    async sendPrintingJob(receipt) {
        const payload = await normalizePayload(this.env, receipt);
        if (odoo.debug) {
            console.debug("[pos_printing_suite] Local Agent payload:", {
                type: payload.type,
                size: payload.data ? String(payload.data).length : 0,
            });
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
                    type: payload.type,
                    printer: this.printerName,
                    data: payload.data,
                }),
            });
        } catch (err) {
            if (err?.name === "AbortError") {
                throw new Error(_t("Local Agent print timed out."));
            }
            if (isLoopbackBlocked(err, this.baseUrl)) {
                const help = buildLoopbackHelpMessage(this.env);
                console.error("[pos_printing_suite] Loopback blocked:", {
                    baseUrl: this.baseUrl,
                    secureContext: window.isSecureContext,
                    error: err?.message,
                });
                throw new Error(help);
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
