/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { toCanvas } from "@point_of_sale/app/utils/html-to-image";

const DEFAULT_RENDER_OPTIONS = {
    backgroundColor: "#ffffff",
    pixelRatio: 1,
    skipFonts: true,
    fontEmbedCSS: "",
    cacheBust: true,
};

function stripDataUrl(data) {
    if (typeof data !== "string") {
        return data;
    }
    const match = data.match(/^data:image\/[a-zA-Z0-9.+-]+;base64,(.*)$/);
    return match ? match[1] : data;
}

function looksLikeBase64Image(data) {
    if (typeof data !== "string") return false;
    const trimmed = data.trim();
    if (!trimmed) return false;
    if (trimmed.startsWith("data:image/")) return true;
    return /^(iVBOR|\/9j|R0lG|Qk|UklGR)/.test(trimmed);
}

function looksLikeHtml(data) {
    if (typeof data !== "string") return false;
    return /<\s*(html|body|div|span|table|section|p|br|img|svg|style|head|meta|title)\b/i.test(
        data
    );
}

function ensurePrintClass(node) {
    if (node?.classList && !node.classList.contains("pos-receipt-print")) {
        node.classList.add("pos-receipt-print");
    }
}

function mountForRender(node) {
    const container = document.createElement("div");
    container.style.position = "fixed";
    container.style.left = "-10000px";
    container.style.top = "0";
    container.style.background = "white";
    container.style.pointerEvents = "none";
    const clone = node.cloneNode(true);
    ensurePrintClass(clone);
    container.appendChild(clone);
    document.body.appendChild(container);
    return {
        node: clone,
        cleanup: () => container.remove(),
    };
}

async function renderElementToImage(element) {
    const { node, cleanup } = mountForRender(element);
    try {
        const canvas = await toCanvas(node, DEFAULT_RENDER_OPTIONS);
        return canvas?.toDataURL ? canvas.toDataURL("image/png") : null;
    } finally {
        cleanup();
    }
}

async function htmlToImage(html) {
    const wrapper = document.createElement("div");
    wrapper.innerHTML = html;
    ensurePrintClass(wrapper);
    return await renderElementToImage(wrapper);
}

export async function ensureImagePayload(_env, receipt) {
    if (!receipt) return receipt;
    if (typeof receipt === "string") {
        const trimmed = receipt.trim();
        if (!trimmed) return trimmed;
        if (looksLikeBase64Image(trimmed)) {
            return stripDataUrl(trimmed);
        }
        if (looksLikeHtml(trimmed)) {
            const img = await htmlToImage(trimmed);
            return stripDataUrl(img);
        }
        try {
            const img = await htmlToImage(trimmed);
            return stripDataUrl(img);
        } catch (e) {
            throw new Error(_t("Unable to convert receipt to image."));
        }
    }
    const hasHTMLElement = typeof HTMLElement !== "undefined";
    const element =
        hasHTMLElement && receipt instanceof HTMLElement
            ? receipt
            : hasHTMLElement && receipt?.el instanceof HTMLElement
              ? receipt.el
              : null;
    if (element) {
        const img = await renderElementToImage(element);
        return stripDataUrl(img);
    }
    if (typeof receipt?.image === "string") {
        return stripDataUrl(receipt.image);
    }
    if (receipt?.outerHTML) {
        const img = await htmlToImage(receipt.outerHTML);
        return stripDataUrl(img);
    }
    return receipt;
}
