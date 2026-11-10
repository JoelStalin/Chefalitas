def migrate(cr, version):
    """The e-CF switch moved to res.partner: keep each company's current issuer state, everything else off."""
    cr.execute("""
        UPDATE res_partner p SET l10n_do_ecf_enabled = COALESCE(c.l10n_do_ecf_issuer, FALSE)
          FROM res_company c WHERE c.partner_id = p.id
    """)
    cr.execute("UPDATE res_partner SET l10n_do_ecf_enabled = FALSE WHERE l10n_do_ecf_enabled IS NULL")
    cr.execute("""
        UPDATE res_company c SET l10n_do_ecf_issuer = p.l10n_do_ecf_enabled
          FROM res_partner p WHERE c.partner_id = p.id
    """)
