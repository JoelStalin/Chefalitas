import { patch } from "@web/core/utils/patch";
import { generateQRCodeDataUrl } from "@point_of_sale/utils";
import { GeneratePrinterData } from "@point_of_sale/app/utils/printer/generate_printer_data";

/**
 * JS copy of pos_system's PosOrderReceipt.order_receipt_generate_data (Python):
 * DGII document type and NCF/e-NCF for the receipt header, and the e-CF QR
 * (the rest of the DGII layout comes from pos.order.l10n_do_receipt, computed by the server).
 */
patch(GeneratePrinterData.prototype, {
    generateReceiptData() {
        const data = super.generateReceiptData(...arguments);
        const move = this.order.account_move;
        data.extra_data.l10n_do_document_type =
            this.order.l10n_latam_document_type_report_name ||
            move?.l10n_latam_document_type_id?.report_name ||
            false;
        data.extra_data.l10n_do_ncf =
            this.order.invoice_name || move?.l10n_do_fiscal_number || move?.name || false;
        const qrUrl = this.order.l10n_do_receipt?.qr_url;
        data.image.l10n_do_qr = qrUrl ? generateQRCodeDataUrl(qrUrl) : false;
        return data;
    },
});
