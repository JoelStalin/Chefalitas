import base64

from odoo import fields, models

ESC_INIT = b"\x1b@"
ESC_BOLD_ON, ESC_BOLD_OFF = b"\x1bE\x01", b"\x1bE\x00"
ESC_DOUBLE, ESC_NORMAL = b"\x1d!\x11", b"\x1d!\x00"
ESC_CUT = b"\n\n\n\x1dV\x00"


def _text(value):
    return (value or "").encode("cp437", "replace")


class PosOrder(models.Model):
    _inherit = "pos.order"

    def action_pos_order_paid(self):
        result = super().action_pos_order_paid()
        for order in self:
            order._fripick_capture()
        return result

    def _fripick_capture(self):
        """Captures the order for its company and queues the kitchen ticket and, if enabled, the cashier label."""
        self.ensure_one()
        Order = self.env["fripick.order"].sudo()
        if Order.search_count([("pos_order_id", "=", self.id)]):
            return
        lines = [{"product_id": line.product_id.id, "name": line.full_product_name or line.product_id.display_name,
                  "qty": line.qty, "preparation": self._fripick_preparation(line)} for line in self.lines]
        captured = Order.create({"name": self.pos_reference or self.name, "company_id": self.company_id.id, "pos_order_id": self.id,
                                 "closed_at": fields.Datetime.now(), "amount_total": self.amount_total,
                                 "line_ids": [(0, 0, vals) for vals in lines]})
        company = self.company_id
        jobs = self.env["fripick.print.job"].sudo()
        if company.fripick_kitchen_printer_id:
            jobs |= jobs.create({"printer_id": company.fripick_kitchen_printer_id.id, "kind": "kitchen", "origin": captured.name,
                                 "payload": base64.b64encode(self._fripick_kitchen_ticket(captured)).decode()})
        if company.fripick_labels_enabled and company.fripick_cashier_printer_id:
            jobs |= jobs.create(self._fripick_label_job(captured, company))
        jobs.dispatch()

    def _fripick_preparation(self, line):
        attrs = ", ".join(line.attribute_value_ids.mapped("name")) if "attribute_value_ids" in line._fields else ""
        return " · ".join(filter(None, [attrs, line.customer_note if "customer_note" in line._fields else ""]))

    def _fripick_kitchen_ticket(self, captured):
        """ESC/POS kitchen ticket (80 mm): order, time, table and each item with its preparation."""
        table = self.table_id.display_name if "table_id" in self._fields and self.table_id else ""
        out = [ESC_INIT, ESC_DOUBLE, _text("COMANDA\n"), ESC_NORMAL, ESC_BOLD_ON, _text(f"{captured.name}\n"), ESC_BOLD_OFF,
               _text(f"{fields.Datetime.context_timestamp(self, captured.closed_at):%d/%m %H:%M}  {table}\n"), _text("-" * 42 + "\n")]
        for line in captured.line_ids:
            out += [ESC_BOLD_ON, _text(f"{line.qty:g} x {line.name}\n"), ESC_BOLD_OFF]
            if line.preparation:
                out.append(_text(f"   > {line.preparation}\n"))
        if "general_note" in self._fields and len(self) == 1 and self.general_note:
            out.append(_text(f"Nota: {self.general_note}\n"))
        out.append(ESC_CUT)
        return b"".join(out)

    def _fripick_label_job(self, captured, company):
        printer = company.fripick_cashier_printer_id
        if company.fripick_label_format == "a4":
            pdf, _ = self.env["ir.actions.report"].sudo()._render_qweb_pdf("fripick_orders.action_report_fripick_label_a4", captured.ids)
            return {"printer_id": printer.id, "kind": "label", "content_type": "pdf", "origin": captured.name,
                    "payload": base64.b64encode(pdf).decode()}
        label = [ESC_INIT, ESC_BOLD_ON, ESC_DOUBLE, _text("FRIPICK\n"), ESC_NORMAL, _text(f"{captured.name}\n"), ESC_BOLD_OFF,
                 _text(f"{company.name}\n"), _text(f"{len(captured.line_ids)} artículo(s) · {captured.amount_total:.2f}\n"), ESC_CUT]
        return {"printer_id": printer.id, "kind": "label", "content_type": "raw", "origin": captured.name,
                "payload": base64.b64encode(b"".join(label)).decode()}
