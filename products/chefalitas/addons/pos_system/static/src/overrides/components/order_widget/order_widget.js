import { _t } from "@web/core/l10n/translation";
import { Orderline } from "@point_of_sale/app/generic_components/orderline/orderline";

export class CustomOrderLine extends Orderline {
    static template = "pos_system.CustomOrderLine";
}

import { OrderWidget } from "@point_of_sale/app/generic_components/order_widget/order_widget";

export class CustomOrderWidget extends OrderWidget {
    static template = "pos_system.CustomOrderWidget";

    static components = { 
        ...OrderWidget.components,
        CustomOrderLine
     };
   
}

import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";

OrderReceipt.components = {
    ...OrderReceipt.components,
    CustomOrderWidget,
};