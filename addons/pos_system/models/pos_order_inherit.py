from urllib.parse import unquote_plus

from odoo import api, fields, models

ITBIS_RATES = (18.0, 16.0)
LEGAL_TIP_RATE = 10.0  # propina legal (Ley 16-92 art. 228)


def _is_legal_tip(tax):
    label = f"{tax.name or ''} {tax.tax_group_id.name or ''}".lower()
    return tax.amount == LEGAL_TIP_RATE and "propina" in label


def _fmt_id(vat):
    """RNC 1-30-12345-6 / cedula 001-1234567-8, as printed on DGII documents."""
    digits = "".join(c for c in (vat or "") if c.isdigit())
    if len(digits) == 9:
        return f"{digits[0]}-{digits[1:3]}-{digits[3:8]}-{digits[8]}"
    if len(digits) == 11:
        return f"{digits[:3]}-{digits[3:10]}-{digits[10]}"
    return vat or ""


def _money(amount):
    return f"{amount:,.2f}"


class PosOrder(models.Model):
    _inherit = "pos.order"

    invoice_name = fields.Char(related='account_move.name')
    l10n_latam_document_type_report_name = fields.Char(related='account_move.l10n_latam_document_type_id.report_name')
    # Printed representation of the NCF / e-CF (DGII). Read by the receipt in Python and in the POS.
    l10n_do_receipt = fields.Json(compute="_compute_l10n_do_receipt")

    @api.depends("account_move", "lines", "fiscal_position_id", "payment_ids", "amount_return")
    def _compute_l10n_do_receipt(self):
        for order in self:
            move = order.account_move
            ncf = move and "l10n_do_fiscal_number" in move._fields and move.l10n_do_fiscal_number
            order.l10n_do_receipt = order._l10n_do_receipt_data(move, ncf) if ncf else False

    def _l10n_do_receipt_data(self, move, ncf):
        self.ensure_one()
        tz = self._order_receipt_tz()
        to_local = lambda dt: fields.Datetime.context_timestamp(self.with_context(tz=tz), dt)  # noqa: E731
        company = self.company_id
        partner = move.commercial_partner_id

        lines, gravado, exento, itbis, tip, itbis_rates, tip_rates = [], 0.0, 0.0, 0.0, 0.0, set(), set()
        for line in self.lines:
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            # the preset fiscal position decides the tip: dine-in maps to ITBIS + propina, takeout/delivery to ITBIS
            line_taxes = line.tax_ids_after_fiscal_position
            res = line_taxes.compute_all(price, self.currency_id, line.qty, line.product_id, self.partner_id)
            taxes = {t.id: t for t in line_taxes.flatten_taxes_hierarchy()}
            line_itbis = line_tip = 0.0
            for tax_res in res["taxes"]:
                tax = taxes.get(tax_res["id"]) or self.env["account.tax"].browse(tax_res["id"])
                if _is_legal_tip(tax):
                    line_tip += tax_res["amount"]
                    tip_rates.add(tax.amount)
                elif tax.amount in ITBIS_RATES:
                    line_itbis += tax_res["amount"]
                    itbis_rates.add(tax.amount)
            base = res["total_excluded"]
            if line_itbis:
                gravado += base
            else:
                exento += base
            itbis += line_itbis
            tip += line_tip
            qty = int(line.qty) if float(line.qty).is_integer() else line.qty
            lines.append({
                "qty": qty,
                "name": line.full_product_name or line.product_id.display_name,
                "itbis": _money(line_itbis),
                "total": _money(base + line_itbis),
            })

        is_ecf = (ncf or "").startswith("E")
        stamp = move.l10n_do_electronic_stamp if "l10n_do_electronic_stamp" in move._fields else False
        sign_date = move.l10n_do_ecf_sign_date if "l10n_do_ecf_sign_date" in move._fields else False
        rate = lambda rates: "/".join(f"{r:g}%" for r in sorted(rates))  # noqa: E731
        return {
            "company": {
                "name": company.name,
                "vat": _fmt_id(company.vat),
                "address": ", ".join(p for p in (company.street, company.street2, company.city) if p),
                "phone": company.phone or "",
            },
            "document_type": (move.l10n_latam_document_type_id.report_name or "").upper(),
            "is_ecf": is_ecf,
            "ncf": ncf,
            "date": to_local(self.date_order).strftime("%d/%m/%Y %H:%M:%S"),
            "due_date": move.l10n_do_ncf_expiration_date.strftime("%d/%m/%Y")
            if "l10n_do_ncf_expiration_date" in move._fields and move.l10n_do_ncf_expiration_date else False,
            "register": self.config_id.name,
            "order_ref": self.pos_reference or self.name,
            "table": str(self.table_id.table_number) if "table_id" in self._fields and self.table_id else False,
            "customer": partner.name or "CONSUMIDOR FINAL",
            "customer_vat": _fmt_id(partner.vat) or "N/A",
            "lines": lines,
            "gravado": _money(gravado),
            "exento": _money(exento) if exento else False,
            "itbis": _money(itbis),
            "itbis_rate": rate(itbis_rates) or "18%",
            "tip": _money(tip) if tip else False,
            "tip_rate": rate(tip_rates),
            "total": _money(self.amount_total),
            "payments": [{"name": p.payment_method_id.name, "amount": _money(p.amount)} for p in self.payment_ids],
            "change": _money(self.amount_return) if self.amount_return else False,
            "security_code": move.l10n_do_ecf_security_code if is_ecf and "l10n_do_ecf_security_code" in move._fields else False,
            "sign_date": to_local(sign_date).strftime("%d/%m/%Y %H:%M:%S") if is_ecf and sign_date else False,
            "qr_url": unquote_plus(stamp) if is_ecf and stamp else False,
        }
