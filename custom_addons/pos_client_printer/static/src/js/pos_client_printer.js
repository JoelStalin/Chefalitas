/** @odoo-module */

import { registry } from '@web/core/registry';

registry.category('pos_self_order').add('pos_client_printer', {
    start() {
        console.log('POS client printer bridge loaded.');
    },
});
