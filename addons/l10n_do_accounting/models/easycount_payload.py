"""Construye el payload de EasyCount desde una factura Odoo (account.move)."""
from __future__ import annotations

from typing import Any

ITBIS_RATES = (18.0, 16.0)
LEGAL_TIP_RATE = 10.0  # propina legal (Ley 16-92 art. 228), impuesto adicional DGII 001


def _taxes(line) -> list:
    """Line taxes with group taxes expanded (e.g. "Restaurant" = 18% ITBIS + 10% propina)."""
    flatten = getattr(line.tax_ids, "flatten_taxes_hierarchy", None)
    return list(flatten()) if flatten else list(line.tax_ids)


def _is_legal_tip(tax) -> bool:
    group = getattr(getattr(tax, "tax_group_id", None), "name", "") or ""
    label = f"{getattr(tax, 'name', '') or ''} {group}".lower()
    return tax.amount == LEGAL_TIP_RATE and "propina" in label


def _tax_rate(line) -> tuple[float, bool]:
    rates = [t.amount for t in _taxes(line) if t.amount_type == "percent" and t.amount in ITBIS_RATES]
    if rates:
        return rates[0], False
    return 0.0, True


def build_issue_payload(move, encf: str | None = None) -> dict[str, Any]:
    doc_type = move.l10n_latam_document_type_id
    tipo = doc_type.doc_code_prefix  # E31, E32 ...
    partner = move.partner_id.commercial_partner_id
    foreign = partner.country_id and partner.country_id.code != "DO"
    lines, other_taxes = [], False
    for ln in move.invoice_line_ids.filtered(lambda l: l.display_type == "product"):
        rate, exempt = _tax_rate(ln)
        taxes = _taxes(ln)
        legal_tip = any(_is_legal_tip(t) for t in taxes)
        # ITBIS and the legal tip are modelled by EasyCount; anything else makes it recalculate
        other_taxes = other_taxes or any(
            t.amount not in ITBIS_RATES and t.amount != 0 and not _is_legal_tip(t) for t in taxes
        )
        gross = ln.quantity * ln.price_unit
        lines.append({
            "description": (ln.name or ln.product_id.display_name or "Item")[:200],
            "quantity": ln.quantity,
            "unitPrice": ln.price_unit,
            "itbisRate": rate,
            "discount": gross * (ln.discount or 0.0) / 100.0,
            "exempt": exempt and tipo in ("E44", "E46", "E47"),
            "legalTip": legal_tip,
        })
    payload: dict[str, Any] = {
        "eCfType": tipo,
        "encf": encf or move.l10n_do_fiscal_number or None,
        "odooInvoiceId": move.id,
        "issueDate": str(move.invoice_date or move.date),
        "buyerRnc": None if foreign else (partner.vat or None),
        "buyerForeignId": partner.vat if foreign else None,
        "buyerName": partner.name,
        "currency": move.currency_id.name,
        "exchangeRate": move.currency_id._get_conversion_rate(
            move.currency_id, move.company_id.currency_id, move.company_id, move.invoice_date or move.date
        ),
        "lines": lines,
    }
    if not other_taxes:  # con impuestos no modelados (ni ITBIS ni propina) EasyCount recalcula
        payload["totalAmount"] = abs(move.amount_total)
    if tipo in ("E33", "E34"):
        payload["referenceEncf"] = move.l10n_do_origin_ncf
        origin = move.reversed_entry_id or move.debit_origin_id
        payload["referenceDate"] = str(origin.invoice_date) if origin else str(move.invoice_date)
        payload["modificationCode"] = move.l10n_do_ecf_modification_code or "3"
    return payload
