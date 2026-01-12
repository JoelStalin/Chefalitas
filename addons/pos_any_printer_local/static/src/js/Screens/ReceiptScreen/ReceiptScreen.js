/** @odoo-module **/

import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

patch(ReceiptScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.printerService = useService("local_printer_service");
        this.popup = useService("popup");
    },

    async printReceipt() {
        const isLocalPrintingEnabled = this.pos.config.enable_local_printing;

        if (isLocalPrintingEnabled) {
            if (!this.printerService.state.online) {
                await this.popup.add(ErrorPopup, {
                    title: "Error de Impresión",
                    body: "No se pudo conectar con el agente de impresión local. Asegúrese de que esté instalado y en ejecución.",
                });
                return;
            }

            try {
                const printerName =
                    this.pos.config.local_printer_cashier_name ||
                    this.pos.config.local_printer_name;
                const receipt = this.pos.get_order().export_for_printing();
                const useImage = this.pos.config.local_printer_print_as_image;
                let imageError = null;

                if (useImage) {
                    try {
                        const receiptElement = this.getReceiptElement();
                        const imagePayload = await this.buildReceiptImagePayload(receiptElement);
                        console.log(`Sending receipt image to local printer '${printerName}'.`);
                        await this.printerService.printReceiptImage(printerName, imagePayload);
                    } catch (error) {
                        imageError = error;
                        console.warn("Image printing failed. Falling back to text receipt.", error);
                    }
                }

                if (!useImage || imageError) {
                    // Get the raw receipt data.
                    // In a real scenario, you'd format this into ESC/POS commands.
                    // For this example, we send a simplified text version.
                    const receiptText = this.formatReceiptToText(receipt);
                    console.log(`Sending to local printer '${printerName}':\n`, receiptText);
                    await this.printerService.printReceipt(printerName, receiptText);
                }
                // Kitchen printing (optional)
                const kitchenPrinter = (
                    this.pos.config.local_printer_kitchen_name ||
                    this.pos.config.kitchen_printer_name ||
                    ""
                ).trim();
                if (kitchenPrinter && kitchenPrinter !== printerName) {
                    const kitchenText = this.formatKitchenToText(receipt);
                    console.log(`Sending to kitchen printer '${kitchenPrinter}':\n`, kitchenText);
                    await this.printerService.printReceipt(kitchenPrinter, kitchenText);
                }


            } catch (error) {
                await this.popup.add(ErrorPopup, {
                    title: "Error de Impresión Local",
                    body: `Ocurrió un error al enviar el recibo a la impresora: ${error}`,
                });
            }
        } else {
            // Fallback to the original printing method
            return super.printReceipt(...arguments);
        }
    },

    getReceiptElement() {
        const candidates = [
            ".pos-receipt",
            ".pos-receipt-container .pos-receipt",
            ".receipt-screen .pos-receipt",
        ];
        for (const selector of candidates) {
            const element = this.el?.querySelector(selector);
            if (element) {
                return element;
            }
        }
        throw new Error("No se encontró el elemento del recibo para convertirlo a imagen.");
    },

    applyInlineStyles(sourceNode, targetNode) {
        if (!(sourceNode instanceof Element) || !(targetNode instanceof Element)) {
            return;
        }
        const computedStyle = window.getComputedStyle(sourceNode);
        const styleText = Array.from(computedStyle)
            .map((prop) => `${prop}:${computedStyle.getPropertyValue(prop)};`)
            .join("");
        targetNode.setAttribute("style", styleText);
        const sourceChildren = Array.from(sourceNode.children);
        const targetChildren = Array.from(targetNode.children);
        for (let i = 0; i < sourceChildren.length; i++) {
            this.applyInlineStyles(sourceChildren[i], targetChildren[i]);
        }
    },

    async buildReceiptImagePayload(receiptElement) {
        if (!receiptElement) {
            throw new Error("Elemento de recibo inválido.");
        }

        const rect = receiptElement.getBoundingClientRect();
        const width = Math.ceil(rect.width);
        const height = Math.ceil(rect.height);
        const targetWidth = this.pos.config.local_printer_image_width || width;
        const scale = targetWidth && width ? targetWidth / width : 1;

        const clone = receiptElement.cloneNode(true);
        this.applyInlineStyles(receiptElement, clone);

        const wrapper = document.createElement("div");
        wrapper.setAttribute("xmlns", "http://www.w3.org/1999/xhtml");
        wrapper.style.background = "white";
        wrapper.appendChild(clone);

        const serialized = new XMLSerializer().serializeToString(wrapper);
        const svg = `
            <svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">
                <foreignObject width="100%" height="100%">${serialized}</foreignObject>
            </svg>`;
        const svgData = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;

        const image = new Image();
        await new Promise((resolve, reject) => {
            image.onload = resolve;
            image.onerror = reject;
            image.src = svgData;
        });

        const canvas = document.createElement("canvas");
        const scaledWidth = Math.ceil(width * scale);
        const scaledHeight = Math.ceil(height * scale);
        canvas.width = scaledWidth;
        canvas.height = scaledHeight;
        const ctx = canvas.getContext("2d");
        ctx.fillStyle = "#ffffff";
        ctx.fillRect(0, 0, scaledWidth, scaledHeight);
        ctx.scale(scale, scale);
        ctx.drawImage(image, 0, 0);

        const dataUrl = canvas.toDataURL("image/png");
        const base64 = dataUrl.split(",")[1];
        return {
            mime: "image/png",
            data: base64,
            width: scaledWidth,
            height: scaledHeight,
        };
    },

    /**
     * Helper function to format the receipt object into a simple string.
     * In a real-world application, this would be a more complex function
     * that generates a specific printer language (like ESC/POS).
     */
    formatReceiptToText(receipt) {
        let text = `${receipt.company.name}\n`;
        text += `${receipt.company.street || ''}\n\n`;
        text += `Order: ${receipt.name}\n`;
        text += `Date: ${receipt.date.localestring}\n\n`;

        receipt.orderlines.forEach(line => {
            text += `${line.product_name} (${line.quantity})`.padEnd(20);
            text += `${line.price_with_tax.toFixed(2)}\n`;
        });

        text += '\n' + 'Subtotal:'.padEnd(20) + `${receipt.subtotal.toFixed(2)}\n`;
        text += 'Tax:'.padEnd(20) + `${receipt.total_tax.toFixed(2)}\n`;
        text += 'TOTAL:'.padEnd(20) + `${receipt.total_with_tax.toFixed(2)}\n`;

        return text;
    },

    formatKitchenToText(receipt) {
        let text = `Cocina - ${receipt.name}\n`;
        if (receipt.table) {
            text += `Mesa: ${receipt.table}\n`;
        }
        text += `Fecha: ${receipt.date.localestring}\n\n`;

        receipt.orderlines.forEach(line => {
            text += `${line.product_name} x${line.quantity}\n`;
            if (line.note) {
                text += `  Nota: ${line.note}\n`;
            }
        });

        return text;
    },
});
