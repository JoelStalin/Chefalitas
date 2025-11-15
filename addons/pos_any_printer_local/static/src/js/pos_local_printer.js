odoo.define('pos_any_printer_local.local_printer', function(require){
    "use strict";
    const models = require('point_of_sale.models');
    const PosModel = models.PosModel;

    const LOCAL_PRINTER_AGENT_PORT = 9100;
    const LOCAL_AGENT_BASE = `http://127.0.0.1:${LOCAL_PRINTER_AGENT_PORT}`;

    PosModel.prototype._ensureLocalPrinterAvailable = async function() {
        try {
            const cfg = this.config;
            if (!cfg || !cfg.local_printer_name) {
                console.log('No hay nombre de impresora local configurado.');
                return;
            }
            const resp = await fetch(`${LOCAL_AGENT_BASE}/printers`, {method: 'GET'});
            if (!resp.ok) {
                console.warn('No hay agente local de impresión disponible en', LOCAL_AGENT_BASE);
                return;
            }
            const printers = await resp.json();
            console.log('Impresoras locales detectadas:', printers);

            const desired = printers.find(p => p.name === cfg.local_printer_name || (p.name && p.name.includes(cfg.local_printer_name)));
            if (desired) {
                this.local_printer_available = true;
                this.local_printer_name_actual = desired.name;
                console.log('Impresora local encontrada:', desired.name);
            } else {
                console.warn('Impresora configurada no encontrada en la máquina local:', cfg.local_printer_name);
            }
        } catch (err) {
            console.warn('Error comprobando agente local de impresión:', err);
        }
    };

    PosModel.prototype.print_on_local_printer = async function({data, mime='raw', filename='job.bin'}) {
        const cfg = this.config;
        if (!cfg || !cfg.local_printer_name) {
            throw new Error('No hay impresora local configurada en POS.');
        }

        const targetName = cfg.local_printer_name;
        const url = `${LOCAL_AGENT_BASE}/print`;

        let data_base64;
        if (typeof data === 'string') {
            data_base64 = btoa(unescape(encodeURIComponent(data)));
        } else if (data instanceof Uint8Array || data instanceof ArrayBuffer) {
            let bytes = data instanceof ArrayBuffer ? new Uint8Array(data) : data;
            let str = '';
            for (let i=0;i<bytes.length;i++) str += String.fromCharCode(bytes[i]);
            data_base64 = btoa(str);
        } else {
            // try JSON stringify
            data_base64 = btoa(String(data));
        }

        const payload = {
            printer_name: targetName,
            mime: mime,
            filename: filename,
            data_base64: data_base64
        };

        const resp = await fetch(url, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        if (!resp.ok) {
            const txt = await resp.text();
            throw new Error(`Error agente local: ${resp.status} ${txt}`);
        }
        const json = await resp.json();
        if (json.result !== 'ok') {
            throw new Error('Impresión fallida: ' + (json.error || JSON.stringify(json)));
        }
        return true;
    };

    // Hook: intentar comprobar impresora al iniciar POS
    const _posmodel_init = PosModel.prototype.initialize;
    PosModel.prototype.initialize = function(session, attributes) {
        _posmodel_init.apply(this, arguments);
        setTimeout(() => {
            try { this._ensureLocalPrinterAvailable(); } catch (e) { console.error(e); }
        }, 1000);
    };

});
