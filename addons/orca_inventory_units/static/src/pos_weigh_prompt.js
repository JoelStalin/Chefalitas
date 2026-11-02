/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { NumberPopup } from "@point_of_sale/app/components/popups/number_popup/number_popup";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";

/**
 * Products sold by weight ("to weigh") with no electronic scale connected: ask for the quantity (pounds) as soon as the
 * product is chosen, instead of adding 1 and making the cashier edit it. With a scale (this.scale) Odoo's own flow runs.
 * Any failure here falls back to Odoo's default behavior so the POS never stops selling.
 */
patch(PosStore.prototype, {
    async handleWeighableProduct(values, order, configure) {
        try {
            const tmpl = values.product_tmpl_id;
            if (configure && tmpl && tmpl.to_weight && !this.scale) {
                const unit = values.product_id?.uom_id?.name || tmpl.uom_id?.name || "lb";
                const typed = await makeAwaitable(this.dialog, NumberPopup, {
                    title: _t("%(product)s: cantidad en %(unit)s", { product: tmpl.name, unit }),
                    startingValue: "",
                });
                if (typed === undefined) {
                    return false; // cancelled: do not add the line
                }
                const quantity = parseFloat(String(typed).replace(",", "."));
                if (!(quantity > 0)) {
                    return false;
                }
                values.qty = quantity;
                return true;
            }
        } catch (error) {
            console.warn("ORCA weigh prompt failed, using Odoo's default flow", error);
        }
        return super.handleWeighableProduct(...arguments);
    },
});
