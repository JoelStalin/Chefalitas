/** @odoo-module **/

import { registry } from "@web/core/registry";
import { CharField } from "@web/views/fields/char/char_field"; // Base CharField
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { session } from "@web/session"; // To get company RNC if needed

const { Component, xml, onWillUpdateProps, onMounted, useRef } = owl; // Correct OWL import for v17/18

export class DgiiReportsUrlField extends Component {
    static template = xml`
        <a t-if="formattedUrl" t-att-href="formattedUrl" target="_blank" class="o_field_text">
            <t t-esc="props.value || ''"/>
        </a>
        <span t-else="" class="o_field_text">
            <t t-esc="props.value || ''"/>
        </span>
    `;

    // Define props based on standardFieldProps and add your custom options
    static props = {
        ...standardFieldProps, // Includes props like 'value', 'record', 'name', 'readonly', etc.
        is_rnc: { type: Boolean, optional: true },
        is_modify: { type: Boolean, optional: true }, // Assuming this was from your options
    };

    setup() {
        this.formattedUrl = ""; // Initialize

        onWillUpdateProps(async (nextProps) => {
            this._setFormattedUrl(nextProps);
        });

        onMounted(() => {
            this._setFormattedUrl(this.props);
        });

        this._setFormattedUrl = (propsToUse) => {
            const value = propsToUse.value; // This is the string value of the CharField
            if (!value) {
                this.formattedUrl = "";
                return;
            }

            let urlBase = "";
            let queryParam = "";

            if (propsToUse.is_rnc) {
                urlBase = "https://dgii.gov.do/app/WebApps/ConsultasWeb/consultas/rnc.aspx";
                queryParam = `txtRnc=${encodeURIComponent(value)}`;
            } else if (propsToUse.options && propsToUse.options.is_ncf) { // Example if you add is_ncf
                 urlBase = "https://dgii.gov.do/app/WebApps/ConsultasWeb/consultas/ncf.aspx";
                 const rnc = propsToUse.record.data.company_rnc_field || session.company_rnc || ''; // Get RNC from another field or session
                 queryParam = `txtRnc=${encodeURIComponent(rnc)}&txtNcf=${encodeURIComponent(value)}`;
            } else if (propsToUse.is_modify) {
                // Assuming 'modified_invoice_number' should also be linked to NCF lookup
                // You'll need the RNC of the emitter for this.
                // This part needs clarification on how to get the associated RNC for the modified NCF.
                // For now, let's assume it's similar to a standard NCF lookup if RNC is available.
                urlBase = "https://dgii.gov.do/app/WebApps/ConsultasWeb/consultas/ncf.aspx";
                const rnc = propsToUse.record.data.rnc_cedula || propsToUse.record.data.company_rnc_field || session.company_rnc || '';
                if (rnc) {
                    queryParam = `txtRnc=${encodeURIComponent(rnc)}&txtNcf=${encodeURIComponent(value)}`;
                } else {
                     this.formattedUrl = ""; // Cannot form URL without RNC
                     return;
                }
            }
             else {
                // For fiscal_invoice_number (NCF) and doc_number (if also an NCF)
                // Default to NCF lookup if no specific option is set but it looks like an NCF
                // This assumes you have a way to get the associated RNC
                if (value && value.toString().match(/^B\d{10}$|^E\d{10}$/)) { // Basic NCF pattern check
                    urlBase = "https://dgii.gov.do/app/WebApps/ConsultasWeb/consultas/ncf.aspx";
                    const rnc = propsToUse.record.data.rnc_cedula || propsToUse.record.data.company_rnc_field || session.company_rnc || '';
                     if (rnc) {
                        queryParam = `txtRnc=${encodeURIComponent(rnc)}&txtNcf=${encodeURIComponent(value)}`;
                    } else {
                        this.formattedUrl = ""; // Cannot form URL without RNC
                        return;
                    }
                } else {
                    this.formattedUrl = ""; // Not a recognized pattern for URL
                    return;
                }
            }
            this.formattedUrl = `${urlBase}?${queryParam}`;
        };
    }
}

// Register the new OWL field widget
registry.category("fields").add("dgii_reports_url", {
    component: DgiiReportsUrlField,
    displayName: "DGII Report URL",
    supportedTypes: ["char"], // Explicitly state it's for char fields
    extractProps: ({ attrs, field }) => { // Process options from XML
        return {
            is_rnc: attrs.options && attrs.options.is_rnc,
            is_modify: attrs.options && attrs.options.is_modify,
        };
    },
});