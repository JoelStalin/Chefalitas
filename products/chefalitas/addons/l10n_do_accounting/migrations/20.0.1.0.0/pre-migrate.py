def migrate(cr, version):
    """Drop the blanket unique(company, partner, NCF) constraint inherited from 18.0.

    DGII NCF uniqueness is per issuer: our sales NCF are unique per company and a
    supplier's NCF are unique per supplier. The partial unique indexes created in
    account.move._auto_init already enforce exactly that. The blanket constraint wrongly
    rejected a purchase whose supplier NCF equals one of our own sales NCF for the same
    partner (a customer that is also a supplier).
    """
    cr.execute(
        "ALTER TABLE account_move DROP CONSTRAINT IF EXISTS "
        "account_move_unique_l10n_do_fiscal_number_sales"
    )
