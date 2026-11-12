/** @odoo-module **/

// Explicit entrypoint for POS bundles (including legacy /pos/web).
// This guarantees patch modules are evaluated in both debug and minified assets.
import "../overrides/printer_plugin_patch";

