/** @odoo-module **/

// Explicit entrypoint for POS bundles (including legacy /pos/web).
// This guarantees patch modules are evaluated in both debug and minified assets.
import "../overrides/base_printer_patch";
import "../overrides/pos_store_patch";

