/** @odoo-module */

import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    //@override
    export_for_printing(baseUrl, headerData) {
        const result = super.export_for_printing(...arguments);

        if (this.partner_id)
            result.headerData.updated_partner = {
                name: this.partner_id.name,
                vat: this.partner_id.vat,
                address: this.partner_id.contact_address,
            }
            result.headerData.company_address = result.headerData?.company?.partner_id?.contact_address?.replace(result.headerData.company.partner_id.name, "")
            result.headerData.invoice_name = this.raw.invoice_name
            result.headerData.l10n_latam_document_type_report_name = this.raw.l10n_latam_document_type_report_name
            console.log(result)
        return result;
    },
});
