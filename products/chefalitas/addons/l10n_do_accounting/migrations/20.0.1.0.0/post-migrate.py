import logging

_logger = logging.getLogger(__name__)

# l10n_do_accounting xmlid -> official Odoo 20 l10n_do xmlid
DOC_TYPE_MAP = {
    "ecf_fiscal_client": "ecf_31",
    "ecf_consumer_supplier": "ecf_32",
    "ecf_debit_note_client": "ecf_33",
    "ecf_credit_note_client": "ecf_34",
}


def _res_id(cr, module, name):
    cr.execute("SELECT res_id FROM ir_model_data WHERE module = %s AND name = %s", (module, name))
    row = cr.fetchone()
    return row[0] if row else None


def merge_document_types(cr):
    """Odoo 20 l10n_do ships E31-E34; point every reference to the official records and
    drop this module's duplicates (the official records receive this module's fields from
    data/l10n_latam.document.type.csv)."""
    cr.execute("""
        SELECT cl.relname, att.attname
          FROM pg_constraint con
          JOIN pg_class cl ON cl.oid = con.conrelid
          JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = con.conkey[1]
         WHERE con.contype = 'f' AND con.confrelid = 'l10n_latam_document_type'::regclass
    """)
    fks = cr.fetchall()
    merged = 0
    for ours, official in DOC_TYPE_MAP.items():
        old_id = _res_id(cr, "l10n_do_accounting", ours)
        new_id = _res_id(cr, "l10n_do", official)
        if not old_id:
            continue
        if not new_id:
            # official record not there: adopt ours under the official xmlid
            cr.execute("UPDATE ir_model_data SET module = 'l10n_do', name = %s "
                       "WHERE module = 'l10n_do_accounting' AND name = %s", (official, ours))
            continue
        if old_id == new_id:
            continue
        for table, column in fks:
            cr.execute(f'UPDATE "{table}" SET "{column}" = %s WHERE "{column}" = %s', (new_id, old_id))
        cr.execute("DELETE FROM ir_model_data WHERE module = 'l10n_do_accounting' AND name = %s", (ours,))
        cr.execute("DELETE FROM l10n_latam_document_type WHERE id = %s", (old_id,))
        merged += 1
    if merged:
        _logger.info("l10n_do_accounting: merged %s e-CF document types into the official l10n_do ones", merged)


def migrate(cr, version):
    merge_document_types(cr)
