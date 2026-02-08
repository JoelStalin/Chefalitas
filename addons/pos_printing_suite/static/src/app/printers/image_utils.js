/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";

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
    return /<\s*(html|body|div|span|table|section|p|br|img|svg|style|head|meta|title)\b/i.test(data);
}

function getRenderService(env) {
    const services = env?.services || {};
    return (
        services.renderService ||
        services.renderer ||
        services.rendering ||
        services.pos_renderer ||
        services.render
    );
}

async function renderElementToImage(env, element) {
    const service = getRenderService(env);
    const options = { skipFonts: true, cacheBust: true };
    if (service) {
        if (typeof service.renderToImage === "function") {
            try {
                return await service.renderToImage(element, options);
            } catch (e) {
                // fallback below
            }
        }
        if (typeof service.toImage === "function") {
            try {
                return await service.toImage(element, options);
            } catch (e) {
                // fallback below
            }
        }
        if (typeof service.toCanvas === "function") {
            try {
                const canvas = await service.toCanvas(element, options);
                return canvas?.toDataURL ? canvas.toDataURL("image/png") : null;
            } catch (e) {
                // fallback below
            }
        }
    }
    if (globalThis?.htmlToImage?.toPng) {
        return await globalThis.htmlToImage.toPng(element, options);
    }
    if (globalThis?.html2canvas) {
        const canvas = await globalThis.html2canvas(element, { useCORS: true, logging: false });
        return canvas?.toDataURL ? canvas.toDataURL("image/png") : null;
    }
    throw new Error(_t("No image renderer available. Update Odoo POS or enable the render service."));
}

async function htmlToImage(env, html) {
    const container = document.createElement("div");
    container.innerHTML = html;
    container.style.position = "fixed";
    container.style.left = "-10000px";
    container.style.top = "0";
    container.style.background = "white";
    document.body.appendChild(container);
    try {
        return await renderElementToImage(env, container);
    } finally {
        container.remove();
    }
}

export async function ensureImagePayload(env, receipt) {
    if (!receipt) return receipt;
    if (typeof receipt === "string") {
        const trimmed = receipt.trim();
        if (!trimmed) return trimmed;
        if (looksLikeBase64Image(trimmed)) {
            return stripDataUrl(trimmed);
        }
        if (looksLikeHtml(trimmed)) {
            const img = await htmlToImage(env, trimmed);
            return stripDataUrl(img);
        }
        // Best-effort: attempt to render unknown string as HTML
        try {
            const img = await htmlToImage(env, trimmed);
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
        const img = await renderElementToImage(env, element);
        return stripDataUrl(img);
    }
    if (typeof receipt?.image === "string") {
        return stripDataUrl(receipt.image);
    }
    if (receipt?.outerHTML) {
        const img = await htmlToImage(env, receipt.outerHTML);
        return stripDataUrl(img);
    }
    return receipt;
}
