/** @odoo-module **/

import { Component, onWillStart, onMounted, onWillUnmount, useState, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

/**
 * OrcaBarcodeScannerApp (Odoo 20 OWL Component)
 *
 * High-speed barcode scanner client action for stock.picking and stock.inventory:
 * - Intercepts hardware laser gun scans (HID keyboard wedge) and manual input.
 * - Resolves barcodes in <1 ms via L1 Memory + L2 IndexedDB (`orca_barcode_cache`).
 * - Automatically multiplies scanned quantities by `effective_unit_factor` (`qty_per_box`)
 *   when scanning a `product.packaging` master carton / box barcode.
 * - Buffers rapid consecutive scans in `ScanFlushBuffer` and sends a single batch RPC
 *   to avoid repetitive server roundtrips during continuous laser scanning.
 * - Falls back to Open Food Facts / Open Products Facts enrichment on unknown barcodes
 *   and offers 1-click product creation on the fly.
 */
export class OrcaBarcodeScannerApp extends Component {
    static template = "orca_stock_logistics_barcode.OrcaBarcodeScannerApp";
    static props = {
        ...standardActionServiceProps,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.actionService = useService("action");
        this.barcodeCache = useService("orca_barcode_cache");
        this.manualInputRef = useRef("manualBarcodeInput");

        const context = this.props.action?.context || {};
        this.state = useState({
            targetModel: context.default_target_model || context.active_model || "stock.picking",
            targetResId: context.default_picking_id || context.default_inventory_id || context.active_id || 0,
            documentName: "Cargando...",
            documentState: "draft",
            locationId: null,
            locationDestId: null,
            lines: [],
            scanHistory: [],
            pendingEnrichment: null,
            manualBarcode: "",
            manualMultiplier: 1,
            continuousLaserMode: true,
            externalEnrichmentEnabled: true,
            autoFlushDelayMs: 350,
            pendingBatchCount: 0,
            cacheStats: {
                l1MemorySize: 0,
                l1Hits: 0,
                l2IndexedDBHits: 0,
                rpcFallbacks: 0,
            },
            isLoading: true,
            isFlushing: false,
        });

        // Hardware laser scanner HID buffer
        this._hidBuffer = "";
        this._lastKeyTime = 0;
        this._flushTimer = null;
        this._scanFlushQueue = [];

        this._onGlobalKeydown = this._handleGlobalKeydown.bind(this);

        onWillStart(async () => {
            await this._initializeScanner();
        });

        onMounted(() => {
            window.addEventListener("keydown", this._onGlobalKeydown, true);
            this._focusInput();
        });

        onWillUnmount(() => {
            window.removeEventListener("keydown", this._onGlobalKeydown, true);
            if (this._flushTimer) {
                clearTimeout(this._flushTimer);
                this._flushPendingScans();
            }
        });
    }

    async _initializeScanner() {
        this.state.isLoading = true;
        try {
            await this.barcodeCache.warmup(false);
            await this._loadDocumentState();
            this._refreshCacheStats();
        } catch (err) {
            this.notification.add(
                `Error inicializando el escáner ORCA: ${err.message || err}`,
                { type: "danger" }
            );
        } finally {
            this.state.isLoading = false;
        }
    }

    async _loadDocumentState() {
        if (!this.state.targetResId) {
            this.state.documentName = "Modo Escáner Libre (Caché Rápida)";
            this.state.lines = [];
            return;
        }
        const docState = await this.orm.call(
            this.state.targetModel,
            "get_barcode_scanner_state",
            [[this.state.targetResId]]
        );
        if (docState && !docState.error) {
            this.state.documentName = docState.name;
            this.state.documentState = docState.state;
            this.state.locationId = docState.location_id || null;
            this.state.locationDestId = docState.location_dest_id || null;
            this.state.lines = docState.lines || [];
        }
    }

    _refreshCacheStats() {
        this.state.cacheStats = this.barcodeCache.getStats();
    }

    _focusInput() {
        if (this.manualInputRef.el) {
            this.manualInputRef.el.focus();
        }
    }

    /**
     * Global HID laser scanner listener.
     * Laser guns emit characters rapidly (< 45 ms per keystroke) followed by Enter.
     */
    _handleGlobalKeydown(ev) {
        const activeTag = document.activeElement?.tagName;
        if (activeTag === "INPUT" || activeTag === "TEXTAREA" || activeTag === "SELECT") {
            return;
        }

        const now = performance.now();
        if (now - this._lastKeyTime > 120) {
            this._hidBuffer = "";
        }
        this._lastKeyTime = now;

        if (ev.key === "Enter") {
            if (this._hidBuffer.length >= 4) {
                ev.preventDefault();
                ev.stopPropagation();
                const code = this._hidBuffer;
                this._hidBuffer = "";
                this.processBarcode(code, 1.0);
            }
            return;
        }

        if (ev.key && ev.key.length === 1 && !ev.ctrlKey && !ev.altKey && !ev.metaKey) {
            this._hidBuffer += ev.key;
        }
    }

    async onManualFormSubmit(ev) {
        ev.preventDefault();
        const code = (this.state.manualBarcode || "").trim();
        const mult = parseFloat(this.state.manualMultiplier) || 1.0;
        if (!code) {
            return;
        }
        this.state.manualBarcode = "";
        this.state.manualMultiplier = 1;
        await this.processBarcode(code, mult);
        this._focusInput();
    }

    /**
     * Main barcode scan pipeline:
     * 1. Query L1 Memory / L2 IndexedDB (`orca_barcode_cache`)
     * 2. If found:
     *    - Compute `addedUnits = scanQty * effective_unit_factor` (`qty_per_box`)
     *    - Optimistically update UI lines immediately (0 ms latency)
     *    - Enqueue scan into `ScanFlushBuffer` for debounced batch RPC persistence
     * 3. If not found locally and external enrichment found metadata:
     *    - Display 1-click product creation card from Open Food Facts
     */
    async processBarcode(rawBarcode, scanQty = 1.0) {
        const cleanBarcode = String(rawBarcode || "").trim();
        if (!cleanBarcode) {
            return;
        }

        const resolved = await this.barcodeCache.resolve(
            cleanBarcode,
            this.state.externalEnrichmentEnabled
        );
        this._refreshCacheStats();

        if (!resolved || !resolved.matched) {
            this._playFeedbackTone(false);
            const enrichment = resolved?.enrichment || null;
            if (enrichment && enrichment.found) {
                this.state.pendingEnrichment = {
                    barcode: cleanBarcode,
                    typology: resolved.typology || enrichment.typology || "EAN13",
                    name: enrichment.name || `Producto ${cleanBarcode}`,
                    brand: enrichment.brand || "",
                    weightKg: enrichment.weight_kg || 0.0,
                    quantityLabel: enrichment.quantity_label || "",
                    suggestedBoxQty: enrichment.suggested_box_qty || 1.0,
                    sourceApi: enrichment.source_api || "openfoodfacts",
                };
                this.notification.add(
                    `Código ${cleanBarcode} detectado vía Open Food Facts: "${enrichment.name}". Puede crearlo al vuelo.`,
                    { type: "warning" }
                );
            } else {
                this.notification.add(
                    `Código de barras no encontrado: ${cleanBarcode}`,
                    { type: "danger" }
                );
            }
            this._prependHistory({
                barcode: cleanBarcode,
                status: enrichment?.found ? "enrichment_ready" : "not_found",
                productName: enrichment?.name || "Desconocido",
                matchType: resolved?.match_type || "not_found",
                scanQty,
                unitFactor: 1,
                totalUnits: 0,
                cacheLayer: resolved?._cacheLayer || "RPC_FALLBACK",
                timestamp: new Date().toLocaleTimeString(),
            });
            return;
        }

        this._playFeedbackTone(true);
        const unitFactor = parseFloat(resolved.unit_factor) || 1.0;
        const totalUnitsAdded = scanQty * unitFactor;

        // Optimistic UI update on document lines
        this._applyOptimisticLineUpdate(resolved, totalUnitsAdded);

        this._prependHistory({
            barcode: cleanBarcode,
            status: "matched",
            productName: resolved.product_name,
            defaultCode: resolved.default_code || "",
            matchType: resolved.match_type,
            packagingName: resolved.packaging_name || "Unidad",
             packagingType: resolved.packaging_type || "unit",
            scanQty,
            unitFactor,
            totalUnits: totalUnitsAdded,
            cacheLayer: resolved._cacheLayer || "L1_MEMORY",
            timestamp: new Date().toLocaleTimeString(),
        });

        // Queue for batch persistence if attached to a picking or inventory document
        if (this.state.targetResId) {
            this._enqueueScanForBatchFlush(cleanBarcode, scanQty);
        }
    }

    _applyOptimisticLineUpdate(resolved, totalUnitsAdded) {
        const existingLine = this.state.lines.find(
            (l) => l.product_id === resolved.product_id
        );
        if (existingLine) {
            if (this.state.targetModel === "stock.picking") {
                existingLine.quantity = (existingLine.quantity || 0) + totalUnitsAdded;
            } else {
                existingLine.product_qty = (existingLine.product_qty || 0) + totalUnitsAdded;
                existingLine.difference_qty =
                    existingLine.product_qty - (existingLine.theoretical_qty || 0);
            }
            if (resolved.packaging_id) {
                existingLine.packaging_name = resolved.packaging_name;
            }
        } else {
            this.state.lines.unshift({
                id: `temp_${Date.now()}`,
                product_id: resolved.product_id,
                product_name: resolved.product_name,
                barcode: resolved.barcode,
                demand: 0,
                quantity: totalUnitsAdded,
                theoretical_qty: 0,
                product_qty: totalUnitsAdded,
                difference_qty: totalUnitsAdded,
                packaging_name: resolved.packaging_name || "",
                uom_name: resolved.uom_name || "Units",
            });
        }
    }

    _enqueueScanForBatchFlush(barcode, qty) {
        const lastItem = this._scanFlushQueue[this._scanFlushQueue.length - 1];
        if (lastItem && lastItem.barcode === barcode) {
            lastItem.qty += qty;
        } else {
            this._scanFlushQueue.push({ barcode, qty });
        }
        this.state.pendingBatchCount = this._scanFlushQueue.reduce(
            (acc, item) => acc + item.qty,
            0
        );

        if (this._flushTimer) {
            clearTimeout(this._flushTimer);
        }

        if (!this.state.continuousLaserMode) {
            this._flushPendingScans();
        } else {
            this._flushTimer = setTimeout(() => {
                this._flushPendingScans();
            }, this.state.autoFlushDelayMs);
        }
    }

    async _flushPendingScans() {
        if (!this._scanFlushQueue.length || !this.state.targetResId || this.state.isFlushing) {
            return;
        }
        const scansToSend = [...this._scanFlushQueue];
        this._scanFlushQueue = [];
        this.state.pendingBatchCount = 0;
        this.state.isFlushing = true;

        try {
            await this.orm.call(
                this.state.targetModel,
                "action_process_barcode_batch",
                [[this.state.targetResId], scansToSend]
            );
            await this._loadDocumentState();
        } catch (err) {
            this.notification.add(
                `Error sincronizando lote de escaneos: ${err.message || err}`,
                { type: "danger" }
            );
        } finally {
            this.state.isFlushing = false;
        }
    }

    async onCreateProductOnTheFly() {
        if (!this.state.pendingEnrichment) {
            return;
        }
        const targetBarcode = this.state.pendingEnrichment.barcode;
        try {
            const created = await this.barcodeCache.createProductFromEnrichment(targetBarcode);
            if (created && created.matched) {
                this.notification.add(
                    `Producto "${created.product_name}" creado y almacenado en caché IndexedDB.`,
                    { type: "success" }
                );
                this.state.pendingEnrichment = null;
                this._refreshCacheStats();
                // Automatically register 1 scan of the newly created product
                await this.processBarcode(targetBarcode, 1.0);
            }
        } catch (err) {
            this.notification.add(
                `No se pudo crear el producto al vuelo: ${err.message || err}`,
                { type: "danger" }
            );
        }
    }

    onDismissEnrichment() {
        this.state.pendingEnrichment = null;
    }

    async onForceCacheWarmup() {
        this.state.isLoading = true;
        try {
            await this.barcodeCache.clearCache();
            const res = await this.barcodeCache.warmup(true);
            this._refreshCacheStats();
            this.notification.add(
                `Caché IndexedDB actualizada (${res.count || 0} códigos indexados).`,
                { type: "success" }
            );
        } finally {
            this.state.isLoading = false;
            this._focusInput();
        }
    }

    async onFlushNowClick() {
        await this._flushPendingScans();
        this._focusInput();
    }

    _prependHistory(entry) {
        this.state.scanHistory.unshift(entry);
        if (this.state.scanHistory.length > 40) {
            this.state.scanHistory.pop();
        }
    }

    /**
     * Synthesizes a short WebAudio beep for instant warehouse operator feedback
     * without requiring external audio asset files.
     */
    _playFeedbackTone(success = true) {
        try {
            const AudioCtx = window.AudioContext || window.webkitAudioContext;
            if (!AudioCtx) {
                return;
            }
            const ctx = new AudioCtx();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = success ? "sine" : "sawtooth";
            osc.frequency.value = success ? 1046.5 : 220.0;
            gain.gain.value = 0.08;
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + (success ? 0.07 : 0.18));
        } catch {
            // AudioContext may be blocked before user gesture
        }
    }
}

registry.category("actions").add("orca_stock_barcode_scanner_client_action", OrcaBarcodeScannerApp);
