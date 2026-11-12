/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";

patch(ControlButtons.prototype, {
    setup() {
        super.setup(...arguments);
        this.scaleOrm = useService("orm");
    },
    async captureScaleWeight() {
        const line = this.currentOrder?.getSelectedOrderline();
        if (!line) {
            this.dialog.add(AlertDialog, {
                title: _t("Scale"),
                body: _t("Select a product sold by weight first."),
            });
            return;
        }
        try {
            const result = await this.scaleOrm.call("pos.scale.device", "read_for_pos", [
                this.pos.config.id,
                line.product_id.id,
            ]);
            line.setQuantity(result.quantity);
            this.notification.add(
                _t("Weight captured: %s %s", result.quantity.toFixed(3), result.unit),
                { type: "success" }
            );
        } catch (error) {
            this.dialog.add(AlertDialog, {
                title: _t("Scale reading unavailable"),
                body: error.data?.message || error.message || _t("Check the scale connection."),
            });
        }
    },
});
