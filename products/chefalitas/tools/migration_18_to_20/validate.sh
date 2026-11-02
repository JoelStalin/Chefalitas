#!/usr/bin/env bash
# Compare the Odoo 18 production copy with the imported Odoo 20 database. Exit 1 on any difference.
#   SRC_CONTAINER=chefmig-src-pg SRC_DB=chefalitas_src DST_CONTAINER=ecfcert-odoo-db-1 DST_DB=chef20 ./validate.sh
set -uo pipefail
SRC_CONTAINER=${SRC_CONTAINER:-chefmig-src-pg}; SRC_DB=${SRC_DB:-chefalitas_src}
DST_CONTAINER=${DST_CONTAINER:-ecfcert-odoo-db-1}; DST_DB=${DST_DB:-chef20}
fail=0
check() {
  local name=$1 sql=$2
  local s d
  s=$(docker exec -i "$SRC_CONTAINER" psql -U odoo -d "$SRC_DB" -At -F'|' -c "$sql" | sort)
  d=$(docker exec -i "$DST_CONTAINER" psql -U odoo -d "$DST_DB" -At -F'|' -c "$sql" | sort)
  if [ "$s" == "$d" ]; then echo "OK    $name"; else echo "DIFF  $name"; diff <(echo "$s") <(echo "$d") | head -5; fail=1; fi
}
check "trial balance (posted, by account code)" \
  "select a.code_store->>'1', round(sum(l.balance),2) from account_move_line l join account_account a on a.id=l.account_id join account_move m on m.id=l.move_id where m.state='posted' group by 1"
check "moves by type/state" "select move_type, state, count(*) from account_move group by 1,2"
check "move names and totals" "select name, round(amount_total_signed,2) from account_move where name <> '/'"
check "customer invoices total" "select count(*), round(sum(amount_total_signed),2) from account_move where move_type='out_invoice' and state='posted'"
check "reconciliations" "select count(*), count(distinct full_reconcile_id) from account_partial_reconcile"
check "pos orders" "select state, count(*), round(sum(amount_total),2), round(sum(amount_tax),2), round(sum(amount_paid),2) from pos_order group by 1"
check "pos lines" "select count(*), round(sum(price_subtotal_incl),2) from pos_order_line"
check "pos payments" "select count(*), round(sum(amount),2) from pos_payment"
check "pos sessions" "select count(*) from pos_session"
check "employees" "select count(*) from hr_employee where active"
exit $fail
