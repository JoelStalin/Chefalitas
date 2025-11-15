odoo.define('pos_any_printer_local.printer_selector', function(require){
    'use strict';
    const Gui = require('point_of_sale.Gui');
    const PosModel = require('point_of_sale.models').PosModel;
    const models = require('point_of_sale.models');
    const screens = require('point_of_sale.screens');
    const core = require('web.core');

    const LOCAL_PRINTER_AGENT_PORT = 9100;
    const LOCAL_AGENT_BASE = `http://127.0.0.1:${LOCAL_PRINTER_AGENT_PORT}`;

    // Add a small button on the POS config screen or a popup accessible from POS
    // We'll add a popup that lists printers and lets user select one and save to pos.config
    const _posmodel_init = PosModel.prototype.initialize;
    PosModel.prototype.initialize = function(session, attrs) {
        _posmodel_init.apply(this, arguments);
        // nothing else; the selector can be invoked from the POS UI by calling show_printer_selector
    };

    // Utility: fetch printers from local agent
    async function fetchLocalPrinters() {
        try {
            const resp = await fetch(`${LOCAL_AGENT_BASE}/printers`, {method: 'GET'});
            if (!resp.ok) {
                return {ok: false, error: 'Agente local no disponible'};
            }
            const data = await resp.json();
            return {ok: true, printers: data};
        } catch (e) {
            return {ok: false, error: String(e)};
        }
    }

    // Show popup to select printer; pos_config_id is current config id
    PosModel.prototype.show_printer_selector = async function(pos_config_id) {
        const self = this;
        const result = await fetchLocalPrinters();
        if (!result.ok) {
            self.gui.show_popup('error', {
                title: 'No se detectó agente local',
                body: 'Asegúrate de que el agente de impresión esté instalado y corriendo en esta máquina.'
            });
            return;
        }
        const printers = result.printers || [];
        // Build a simple selection popup using built-in popups
        this.gui.show_popup('selection', {
            'title': 'Seleccionar impresora local',
            'list': printers.map(p => ({label: p.name, item: p})),
            'confirm': function(item) {
                const selected = item && item.item && item.item.name;
                if (!selected) return;
                // Save via controller
                self.rpc('/pos_local_printer/save_printer', {pos_config_id: pos_config_id, printer_name: selected}).then(function(resp){
                    if (resp && resp.result === 'ok') {
                        self.gui.show_popup('confirm', {
                            title: 'Impresora guardada',
                            body: 'Impresora local seleccionada y guardada en la configuración del POS.'
                        });
                        // update local config value if available
                        if (self.config) {
                            self.config.local_printer_name = selected;
                        }
                    } else {
                        self.gui.show_popup('error', {
                            title: 'Error guardando impresora',
                            body: resp.error || 'Error desconocido'
                        });
                    }
                }).catch(function(err){
                    self.gui.show_popup('error', {
                        title: 'Error guardando impresora',
                        body: String(err)
                    });
                });
            }
        });
    };

    // Add a keyboard shortcut or global menu item: when pressing Ctrl+P in POS, open selector (helpful)
    document.addEventListener('keydown', function(e){
        if ((e.ctrlKey || e.metaKey) && e.key && e.key.toLowerCase() === 'p') {
            try {
                const pos = window.posmodel || (window.opener && window.opener.posmodel);
                if (pos) {
                    const cfg_id = pos.config && pos.config.id;
                    if (cfg_id) {
                        pos.show_printer_selector(cfg_id);
                    }
                }
            } catch (err) { console.warn('Shortcut open selector failed', err); }
        }
    });
});
