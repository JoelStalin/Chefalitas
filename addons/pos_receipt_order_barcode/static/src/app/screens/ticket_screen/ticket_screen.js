import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { useBarcodeReader } from "@point_of_sale/app/hooks/barcode_reader_hook";

/**
 * En la pantalla de pedidos, un código de barras que no es de producto, cliente ni descuento se toma como la
 * referencia de un pedido (el que imprime el recibo): se abre ese pedido para hacer la devolución.
 */
patch(TicketScreen.prototype, {
    setup() {
        super.setup(...arguments);
        useBarcodeReader({ error: (parsed) => this.onScanReceiptBarcode(parsed?.code) });
    },

    async onScanReceiptBarcode(code) {
        const reference = (code || "").trim();
        if (!reference) {
            return;
        }
        const orders = await this.pos.data.loadServerOrders([["pos_reference", "=", reference]]);
        const order = orders[0];
        if (order) {
            this.state.filter = "SYNCED";
            this.setSelectedOrder(order);
        } else {
            this.env.services.notification.add(_t("No se encontró ningún pedido con el código %s.", reference), {
                type: "warning",
            });
        }
    },
});
