-- Exporta de Odoo 18 lo necesario para que los usuarios vuelvan a entrar en Odoo 20: compañías, contactos y usuarios (con su clave cifrada y grupos).
SELECT json_build_object(
  'companies', (SELECT json_agg(row_to_json(c)) FROM (
      SELECT co.id, co.name, co.partner_id, cur.name AS currency
      FROM res_company co LEFT JOIN res_currency cur ON cur.id = co.currency_id ORDER BY co.id) c),
  'partners', (SELECT json_agg(row_to_json(p)) FROM (
      SELECT pa.id, pa.name, pa.vat, pa.email, pa.phone, pa.street, pa.street2, pa.city, pa.zip,
             pa.is_company, pa.parent_id, pa.type, pa.active, pa.company_id, pa.ref, pa.comment::text AS comment,
             pa.customer_rank, pa.supplier_rank, ct.code AS country
      FROM res_partner pa LEFT JOIN res_country ct ON ct.id = pa.country_id
      WHERE pa.id NOT IN (SELECT partner_id FROM res_users WHERE login IN ('__system__', 'default', 'public', 'portaltemplate'))
      ORDER BY pa.parent_id NULLS FIRST, pa.id) p),
  'users', (SELECT json_agg(row_to_json(u)) FROM (
      SELECT us.id, us.login, us.partner_id, us.active, us.password, us.company_id,
             (SELECT json_agg(d.module || '.' || d.name) FROM res_groups_users_rel r
                JOIN ir_model_data d ON d.model = 'res.groups' AND d.res_id = r.gid WHERE r.uid = us.id) AS groups,
             (SELECT json_agg(rc.cid) FROM res_company_users_rel rc WHERE rc.user_id = us.id) AS companies
      FROM res_users us WHERE us.id > 2 AND us.share = false AND us.login NOT IN ('default', 'public', 'portaltemplate', '__system__')
      ORDER BY us.id) u)
);
