/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import * as htmlToImage from "@point_of_sale/app/utils/html-to-image";

const FORCE_OPTIONS = {
    skipFonts: true,
    fontEmbedCSS: "",
    cacheBust: true,
};

if (odoo.debug) {
    console.debug("[pos_printing_suite] html_to_image_patch loaded");
}

patch(htmlToImage, {
    async toCanvas(node, options = {}) {
        const merged = { ...options, ...FORCE_OPTIONS };
        return await super.toCanvas(node, merged);
    },
});
