/** @odoo-module **/

import { registry } from "@web/core/registry";
import { reactive } from "@odoo/owl";

const localPrinterService = {
    dependencies: [],
    start(env) {
        const state = reactive({
            online: false,
            printers: [],
            lastError: null,
        });

        const getBaseUrl = () => {
            const config = env.services.pos?.config || {};
            return (config.agent_url || "http://127.0.0.1:9060").replace(/\/$/, "");
        };

        const fetchJSON = async (path, opts = {}) => {
            const baseUrl = getBaseUrl();
            const res = await fetch(`${baseUrl}${path}`, {
                ...opts,
                headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
            });
            const txt = await res.text();
            if (!res.ok) {
                throw new Error(txt || `HTTP ${res.status}`);
            }
            try {
                return txt ? JSON.parse(txt) : {};
            } catch {
                return {};
            }
        };

        const ping = async () => {
            try {
                await fetchJSON("/health", { method: "GET" });
                state.online = true;
                state.lastError = null;
            } catch (e) {
                state.online = false;
                state.lastError = e?.message || String(e);
            }
        };

        const refreshPrinters = async () => {
            try {
                const data = await fetchJSON("/printers", { method: "GET" });
                state.printers = data.printers || [];
            } catch (e) {
                // No bloquear: solo registrar
                state.lastError = e?.message || String(e);
            }
        };

        // boot
        ping();
        refreshPrinters();
        setInterval(ping, 3000);

        const b64utf8 = (s) => btoa(unescape(encodeURIComponent(s || "")));

        return {
            state,
            async getPrinters() {
                await refreshPrinters();
                return state.printers;
            },
            async printRaw(printerName, rawBase64) {
                const payload = { type: "raw", printer: printerName, data: rawBase64 };
                await fetchJSON("/print", { method: "POST", body: JSON.stringify(payload) });
            },
            async printReceipt(printerName, dataText) {
                await this.printRaw(printerName, b64utf8(dataText));
            },
            async printImage(printerName, imgBase64) {
                // imgBase64: sin prefijo data:image/png;base64,...
                const clean = (imgBase64 || "").includes("base64,") ? imgBase64.split("base64,")[1] : imgBase64;
                const payload = { type: "image", printer: printerName, data: clean };
                await fetchJSON("/print", { method: "POST", body: JSON.stringify(payload) });
            },
        };
    },
};

registry.category("services").add("local_printer_service", localPrinterService);
