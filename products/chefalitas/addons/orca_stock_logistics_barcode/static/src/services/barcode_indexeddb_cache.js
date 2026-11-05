/** @odoo-module */
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

const DB_NAME = "orca_barcode_cache_v20";
const DB_VERSION = 1;
const STORE_CATALOG = "catalog_by_barcode";
const STORE_QUEUE = "offline_scan_queue";

/**
 * Dual-Layer Barcode Cache (L1 Memory Map + L2 IndexedDB) for Odoo 20.
 *
 * Eliminates repetitive RPC roundtrips during continuous laser gun bursts
 * (50+ scans/sec) while persisting product & multi-packaging factors locally.
 */
export class OrcaBarcodeIndexedDBCache {
    constructor() {
        this.memoryMap = new Map();
        this.dbPromise = null;
        this.lastSyncTimestamp = null;
        this.hits = 0;
        this.misses = 0;
    }

    async openDB() {
        if (this.dbPromise) {
            return this.dbPromise;
        }
        if (typeof indexedDB === "undefined") {
            return null;
        }
        this.dbPromise = new Promise((resolve) => {
            const req = indexedDB.open(DB_NAME, DB_VERSION);
            req.onupgradeneeded = (event) => {
                const db = event.target.result;
                if (!db.objectStoreNames.contains(STORE_CATALOG)) {
                    const catalogStore = db.createObjectStore(STORE_CATALOG, { keyPath: "barcode" });
                    catalogStore.createIndex("product_id", "product_id", { unique: false });
                    catalogStore.createIndex("match_type", "match_type", { unique: false });
                }
                if (!db.objectStoreNames.contains(STORE_QUEUE)) {
                    db.createObjectStore(STORE_QUEUE, { keyPath: "batch_id", autoIncrement: true });
                }
            };
            req.onsuccess = () => resolve(req.result);
            req.onerror = () => resolve(null);
        });
        return this.dbPromise;
    }

    async hydrateMemoryFromIndexedDB() {
        const db = await this.openDB();
        if (!db) {
            return 0;
        }
        return new Promise((resolve) => {
            const tx = db.transaction([STORE_CATALOG], "readonly");
            const store = tx.objectStore(STORE_CATALOG);
            const req = store.getAll();
            req.onsuccess = () => {
                const rows = req.result || [];
                for (const row of rows) {
                    if (row && row.barcode) {
                        this.memoryMap.set(row.barcode, row);
                    }
                }
                resolve(rows.length);
            };
            req.onerror = () => resolve(0);
        });
    }

    async putCatalogEntries(entries) {
        if (!Array.isArray(entries) || !entries.length) {
            return 0;
        }
        for (const entry of entries) {
            if (entry && entry.barcode) {
                this.memoryMap.set(entry.barcode, entry);
            }
        }
        const db = await this.openDB();
        if (!db) {
            return entries.length;
        }
        return new Promise((resolve) => {
            const tx = db.transaction([STORE_CATALOG], "readwrite");
            const store = tx.objectStore(STORE_CATALOG);
            for (const entry of entries) {
                if (entry && entry.barcode) {
                    store.put(entry);
                }
            }
            tx.oncomplete = () => resolve(entries.length);
            tx.onerror = () => resolve(entries.length);
        });
    }

    async warmupFromBackend(limit = 5000) {
        await this.hydrateMemoryFromIndexedDB();
        try {
            const payload = await rpc("/orca/barcode/warmup", {
                limit,
                offset: 0,
                write_date_after: this.lastSyncTimestamp || false,
            });
            if (payload && Array.isArray(payload.entries)) {
                await this.putCatalogEntries(payload.entries);
                this.lastSyncTimestamp = payload.synced_at || null;
            }
            return {
                cachedCount: this.memoryMap.size,
                syncedAt: this.lastSyncTimestamp,
            };
        } catch {
            return {
                cachedCount: this.memoryMap.size,
                syncedAt: this.lastSyncTimestamp,
                offline: true,
            };
        }
    }

    /**
     * Instant (< 1ms) lookup from L1 memory Map or L2 IndexedDB, falling back
     * to a single backend resolve RPC only on cache miss.
     */
    async resolveBarcode(barcode, { autoEnrich = true } = {}) {
        const clean = (barcode || "").trim();
        if (!clean) {
            return { found: false, barcode: "" };
        }
        // 1. L1 Memory Hit
        if (this.memoryMap.has(clean)) {
            this.hits += 1;
            return { ...this.memoryMap.get(clean), cache_layer: "L1_MEMORY" };
        }

        // 2. L2 IndexedDB Hit
        const db = await this.openDB();
        if (db) {
            const idbHit = await new Promise((resolve) => {
                const tx = db.transaction([STORE_CATALOG], "readonly");
                const req = tx.objectStore(STORE_CATALOG).get(clean);
                req.onsuccess = () => resolve(req.result || null);
                req.onerror = () => resolve(null);
            });
            if (idbHit) {
                this.memoryMap.set(clean, idbHit);
                this.hits += 1;
                return { ...idbHit, cache_layer: "L2_INDEXEDDB" };
            }
        }

        // 3. Backend Indexed Search + External API Fallback
        this.misses += 1;
        const remote = await rpc("/orca/barcode/resolve", {
            barcode: clean,
            auto_enrich: autoEnrich,
        });
        if (remote && remote.found) {
            await this.putCatalogEntries([remote]);
            return { ...remote, cache_layer: "BACKEND_RPC" };
        }
        return remote || { found: false, barcode: clean };
    }

    getStats() {
        const total = this.hits + this.misses;
        return {
            catalogSize: this.memoryMap.size,
            hits: this.hits,
            misses: this.misses,
            hitRatePct: total > 0 ? Math.round((this.hits / total) * 1000) / 10 : 100.0,
            lastSyncTimestamp: this.lastSyncTimestamp,
        };
    }
}

export const orcaBarcodeCacheService = {
    dependencies: [],
    start() {
        return new OrcaBarcodeIndexedDBCache();
    },
};

registry.category("services").add("orca_barcode_cache", orcaBarcodeCacheService);
