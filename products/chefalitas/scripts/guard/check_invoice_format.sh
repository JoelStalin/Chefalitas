#!/usr/bin/env bash
# Guardian del formato de factura validado en la certificacion DGII (Chefalitas 51117e3, PR #47).
# Falla si alguien cambia las plantillas protegidas, quita lo que exige la DGII o toca el diseno base de TODOS los reportes.
#   bash scripts/guard/check_invoice_format.sh            verifica
#   bash scripts/guard/check_invoice_format.sh --update   regenera la huella (solo tras un cambio de formato APROBADO)
set -uo pipefail
cd "$(dirname "$0")/../.."
VIEWS=addons/l10n_do_accounting/views
LOCK=scripts/guard/invoice_format.sha256
PROTECTED="$VIEWS/report_invoice.xml $VIEWS/report_invoice_preview.xml"

if [ "${1:-}" = "--update" ]; then
  sha256sum $PROTECTED > "$LOCK"; echo "huella actualizada: $LOCK"; exit 0
fi

fail=0
# 1) las plantillas protegidas deben ser exactamente las validadas
if ! sha256sum --check --quiet "$LOCK" 2>/dev/null; then
  echo "ERROR: el formato de factura validado fue modificado ($PROTECTED)."
  echo "       Si el cambio esta APROBADO por el titular: bash scripts/guard/check_invoice_format.sh --update"
  echo "       y el commit/PR debe incluir la marca [formato-factura-aprobado]."
  fail=1
fi
# 2) lo que exige la DGII debe seguir en la factura (QR, codigo de seguridad y fecha de firma)
for needle in "/report/barcode/?barcode_type=QR" l10n_do_electronic_stamp l10n_do_ecf_security_code l10n_do_ecf_sign_date; do
  grep -q -- "$needle" "$VIEWS/report_invoice.xml" || { echo "ERROR: la factura ya no contiene '$needle' (exigido por la DGII)."; fail=1; }
done
# 3) ninguna plantilla del modulo puede alterar el diseno base de todos los reportes de Odoo
if grep -rEn 'inherit_id="web\.(external_layout_body|report_layout|html_container|minimal_layout)"' addons/l10n_do_accounting --include=*.xml; then
  echo "ERROR: una plantilla de l10n_do_accounting modifica el diseno base de los reportes (afecta a todos los documentos)."
  fail=1
fi
[ "$fail" = 0 ] && echo "formato de factura OK (huella, QR/codigo de seguridad/firma y diseno base intactos)"
exit "$fail"
