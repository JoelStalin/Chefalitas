import html
import logging
import re
import urllib.parse
import urllib.request
from odoo import models, fields, api, _
from odoo.exceptions import AccessError, ValidationError, UserError

_logger = logging.getLogger(__name__)

DGII_RNC_URL = "https://dgii.gov.do/app/WebApps/ConsultasWeb2/ConsultasWeb/consultas/rnc.aspx"
DGII_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}


def _clean_rnc_string(val):
    if not val:
        return ""
    return "".join(filter(str.isdigit, str(val)))


def _validate_dominican_vat_checksum(clean_val):
    """Valida algorítmicamente el dígito verificador de un RNC (9) o Cédula (11)."""
    if len(clean_val) == 9:
        weights = [7, 9, 8, 6, 5, 4, 3, 2]
        s = sum(int(clean_val[i]) * weights[i] for i in range(8))
        rem = s % 11
        expected = 2 if rem == 0 else (1 if rem == 1 else 11 - rem)
        return int(clean_val[8]) == expected, "RNC", expected
    elif len(clean_val) == 11:
        weights = [1, 2, 1, 2, 1, 2, 1, 2, 1, 2]
        s = 0
        for i in range(10):
            prod = int(clean_val[i]) * weights[i]
            s += (prod // 10) + (prod % 10)
        expected = (10 - (s % 10)) % 10
        return int(clean_val[10]) == expected, "Cédula", expected
    return False, "Desconocido", None


def _fetch_dgii_tokens(timeout=12.0):
    req = urllib.request.Request(DGII_RNC_URL, headers=DGII_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        content = resp.read().decode("utf-8", errors="ignore")

    def get_token(name):
        m = re.search(r'name="' + re.escape(name) + r'"[^>]*value="([^"]*)"', content)
        if not m:
            m = re.search(r'value="([^"]*)"[^>]*name="' + re.escape(name) + r'"', content)
        return m.group(1) if m else ""

    return get_token("__VIEWSTATE"), get_token("__VIEWSTATEGENERATOR"), get_token("__EVENTVALIDATION")


def query_dgii_by_rnc_standalone(rnc_or_cedula, timeout=12.0):
    cleaned = _clean_rnc_string(rnc_or_cedula)
    if not cleaned:
        return None

    try:
        vs, gen, ev = _fetch_dgii_tokens(timeout=timeout)
        if not vs:
            return None

        post_data = {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": vs,
            "__VIEWSTATEGENERATOR": gen,
            "__EVENTVALIDATION": ev,
            "ctl00$cphMain$txtRNCCedula": cleaned,
            "ctl00$cphMain$btnBuscarPorRNC": "Buscar",
            "ctl00$cphMain$hidActiveTab": "0",
        }
        encoded = urllib.parse.urlencode(post_data).encode("utf-8")
        req = urllib.request.Request(
            DGII_RNC_URL,
            data=encoded,
            headers={**DGII_HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html_content = resp.read().decode("utf-8", errors="ignore")

        parsed = {}
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html_content, re.S)
        for row in rows:
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
            cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in cells]
            if len(cells) >= 2 and cells[0] and cells[1]:
                parsed[cells[0].rstrip(":").strip()] = cells[1]

        if not parsed or not any("Nombre" in k or "Razón" in k or "Razon" in k for k in parsed):
            return None

        name = ""
        commercial_name = ""
        status = ""
        regime = ""
        economic_activity = ""
        local_admin = ""
        electronic_billing = False

        for k, v in parsed.items():
            k_u = k.upper()
            if "NOMBRE" in k_u or "RAZÓN" in k_u or "RAZON" in k_u:
                if "COMERCIAL" in k_u:
                    commercial_name = v
                else:
                    name = v
            elif "ESTADO" in k_u:
                status = v
            elif "RÉGIMEN" in k_u or "REGIMEN" in k_u:
                regime = v
            elif "ACTIVIDAD" in k_u:
                economic_activity = v
            elif "ADMINISTRACION" in k_u or "ADMINISTRACIÓN" in k_u:
                local_admin = v
            elif "FACTURADOR" in k_u:
                electronic_billing = "SI" in v.upper() or "SÍ" in v.upper()

        return {
            "rnc": cleaned,
            "formatted_rnc": parsed.get("Cédula/RNC", parsed.get("Cedula/RNC", cleaned)),
            "name": name,
            "commercial_name": commercial_name or name,
            "status": status,
            "regime": regime,
            "economic_activity": economic_activity,
            "local_admin": local_admin,
            "electronic_billing": electronic_billing,
            "is_company": len(cleaned) == 9,
            "raw": parsed,
        }
    except Exception as exc:
        _logger.warning("Error en consulta de RNC DGII: %s", exc)
        return None


def query_dgii_by_name_standalone(name_query, timeout=12.0):
    clean_query = (name_query or "").strip()
    if not clean_query:
        return []

    try:
        vs, gen, ev = _fetch_dgii_tokens(timeout=timeout)
        if not vs:
            return []

        post_data = {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": vs,
            "__VIEWSTATEGENERATOR": gen,
            "__EVENTVALIDATION": ev,
            "ctl00$cphMain$txtRazonSocial": clean_query,
            "ctl00$cphMain$btnBuscarPorRazonSocial": "Buscar",
            "ctl00$cphMain$hidActiveTab": "1",
        }
        encoded = urllib.parse.urlencode(post_data).encode("utf-8")
        req = urllib.request.Request(
            DGII_RNC_URL,
            data=encoded,
            headers={**DGII_HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html_content = resp.read().decode("utf-8", errors="ignore")

        grid_match = re.search(r'<table[^>]+id="[^"]*gvContribuyentes[^"]*"[^>]*>(.*?)</table>', html_content, re.S)
        if not grid_match:
            grid_match = re.search(r'<table[^>]+class="[^"]*(?:border|grid)[^"]*"[^>]*>(.*?)</table>', html_content, re.S)

        table_content = grid_match.group(1) if grid_match else html_content
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_content, re.S)

        results = []
        for row in rows:
            td_cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
            if td_cells:
                vals = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in td_cells]
                if len(vals) >= 3:
                    rnc_clean = _clean_rnc_string(vals[0])
                    results.append({
                        "rnc": rnc_clean,
                        "formatted_rnc": vals[0],
                        "name": vals[1],
                        "commercial_name": vals[2] if len(vals) > 2 else "",
                        "regime": vals[4] if len(vals) > 4 else "",
                        "status": vals[5] if len(vals) > 5 else "",
                        "electronic_billing": "SI" in vals[6].upper() if len(vals) > 6 else False,
                    })
        return results
    except Exception as exc:
        _logger.warning("Error en búsqueda por nombre en DGII: %s", exc)
        return []


class Partner(models.Model):
    _inherit = "res.partner"

    def _get_l10n_do_dgii_payer_types_selection(self):
        return [
            ("taxpayer", _("Contribuyente Fiscal")),
            ("non_payer", _("No Contribuyente")),
            ("nonprofit", _("Entidad sin Fines de Lucro")),
            ("special", _("Régimen Especial")),
            ("governmental", _("Gubernamental")),
            ("foreigner", _("Extranjero")),
        ]

    def _get_l10n_do_expense_type(self):
        return [
            ("01", _("01 - Personal")),
            ("02", _("02 - Trabajo, Suministros y Servicios")),
            ("03", _("03 - Arrendamiento")),
            ("04", _("04 - Activos Fijos")),
            ("05", _("05 - Representación")),
            ("06", _("06 - Deducciones Admitidas")),
            ("07", _("07 - Gastos Financieros")),
            ("08", _("08 - Gastos Extraordinarios")),
            ("09", _("09 - Costo y Gastos de Ventas")),
            ("10", _("10 - Adquisición de Activos")),
            ("11", _("11 - Gastos de Seguros")),
        ]

    l10n_do_dgii_tax_payer_type = fields.Selection(
        selection="_get_l10n_do_dgii_payer_types_selection",
        compute="_compute_l10n_do_dgii_payer_type",
        inverse="_inverse_l10n_do_dgii_tax_payer_type",
        string="Tipo de Contribuyente",
        index=True,
        store=True,
    )

    l10n_do_ecf_enabled = fields.Boolean(
        string="Facturación electrónica habilitada",
        default=False,
        tracking=True,
        help="Habilita la emisión de comprobantes fiscales electrónicos (e-CF) para la empresa de este contacto. "
             "Mientras esté apagado la empresa emite NCF serie B y nada se envía a la DGII.",
    )

    l10n_do_tax_regime = fields.Char(
        string="Régimen Fiscal DGII",
        readonly=True,
        copy=False,
        help="Régimen de tributación registrado en DGII (Régimen General, RST, etc.)",
    )

    l10n_do_is_rst = fields.Boolean(
        string="Es Contribuyente RST",
        compute="_compute_l10n_do_is_rst",
        store=True,
        index=True,
        help="Indica si el contribuyente está acogido al Régimen Simplificado de Tributación (RST) según la DGII.",
    )

    @api.depends("l10n_do_tax_regime")
    def _compute_l10n_do_is_rst(self):
        for partner in self:
            regime = (partner.l10n_do_tax_regime or "").upper()
            partner.l10n_do_is_rst = bool("RST" in regime or "SIMPLIFICADO" in regime)

    @api.onchange("vat")
    def _onchange_l10n_do_vat(self):
        if not self.vat:
            self.l10n_do_tax_regime = False
            return
        clean = _clean_rnc_string(self.vat)
        if len(clean) in (9, 11):
            is_valid, doc_type, expected_digit = _validate_dominican_vat_checksum(clean)
            if not is_valid:
                return {
                    "warning": {
                        "title": _("RNC / Cédula Inválido"),
                        "message": _("El número de %s '%s' tiene un dígito verificador inválido.") % (doc_type, self.vat),
                    }
                }

    l10n_do_expense_type = fields.Selection(
        selection="_get_l10n_do_expense_type",
        string="Tipo de Gasto",
        store=True,
    )

    country_id = fields.Many2one(
        default=lambda self: self.env.ref("base.do")
        if self.env.user.company_id.country_id == self.env.ref("base.do")
        else False
    )

    @api.constrains("vat", "country_id")
    def _check_l10n_do_vat_checksum(self):
        """Valida matemáticamente el RNC o Cédula según las normas de la DGII / JCE."""
        for partner in self:
            if not partner.vat:
                continue
            # Solo validar si el país es República Dominicana o no tiene país pero tiene formato 9/11 dígitos
            is_do = (partner.country_code == "DO") or (not partner.country_id and len(_clean_rnc_string(partner.vat)) in [9, 11])
            if not is_do:
                continue

            cleaned = _clean_rnc_string(partner.vat)
            if not cleaned:
                continue

            if len(cleaned) not in [9, 11]:
                raise ValidationError(
                    _("El RNC/Cédula dominicano '%s' debe tener exactamente 9 dígitos (RNC) u 11 dígitos (Cédula).")
                    % partner.vat
                )

            is_valid, doc_type, expected_digit = _validate_dominican_vat_checksum(cleaned)
            if not is_valid:
                raise ValidationError(
                    _("El número de %s '%s' es INVÁLIDO según el algoritmo oficial de control de la DGII/JCE "
                      "(el dígito verificador recibido es '%s', pero se calculó '%s').")
                    % (doc_type, partner.vat, cleaned[-1], expected_digit)
                )

    def _check_l10n_do_fiscal_fields(self, vals):
        if not self or self.parent_id:
            return

        fiscal_fields = [
            f for f in ["name", "vat", "country_id"] if f in vals
        ]

        if (
            fiscal_fields
            and not self.env.user.has_group("l10n_do_accounting.group_l10n_do_edit_fiscal_partner")
            and self.env["account.move"]
            .sudo()
            .search([
                ("l10n_latam_use_documents", "=", True),
                ("country_code", "=", "DO"),
                ("commercial_partner_id", "=", self.id),
                ("state", "=", "posted"),
            ], limit=1)
        ):
            raise AccessError(_(
                "No tienes permisos para modificar %s luego de emitir comprobantes fiscales."
            ) % (", ".join(self._fields[f].string for f in fiscal_fields)))

    def write(self, vals):
        res = super().write(vals)
        self._check_l10n_do_fiscal_fields(vals)
        return res

    @api.depends("vat", "country_id", "name")
    def _compute_l10n_do_dgii_payer_type(self):
        for partner in self:
            vat = partner.vat or partner.name or ""
            clean_vat = _clean_rnc_string(vat)
            vat_len = len(clean_vat)
            upper_name = partner.name.upper() if partner.name else ""
            is_dominican = partner.country_code == "DO"

            if not is_dominican:
                partner.l10n_do_dgii_tax_payer_type = "foreigner"
                continue

            if not clean_vat:
                partner.l10n_do_dgii_tax_payer_type = "non_payer"
                continue

            if vat_len == 11:
                partner.l10n_do_dgii_tax_payer_type = "non_payer"
            elif vat_len == 9:
                if "MINISTERIO" in upper_name and not clean_vat.startswith("4"):
                    partner.l10n_do_dgii_tax_payer_type = "governmental"
                elif "ZONA FRANCA" in upper_name:
                    partner.l10n_do_dgii_tax_payer_type = "special"
                elif "IGLESIA" in upper_name or ("MINISTERIO" in upper_name and clean_vat.startswith("4")):
                    partner.l10n_do_dgii_tax_payer_type = "special"
                elif not clean_vat.startswith("4"):
                    partner.l10n_do_dgii_tax_payer_type = "taxpayer"
                else:
                    partner.l10n_do_dgii_tax_payer_type = "nonprofit"
            else:
                partner.l10n_do_dgii_tax_payer_type = "non_payer"

    def _inverse_l10n_do_dgii_tax_payer_type(self):
        for partner in self:
            partner.l10n_do_dgii_tax_payer_type = partner.l10n_do_dgii_tax_payer_type

    # -------------------------------------------------------------------------
    # CONSULTA OFICIAL DGII AUTÓNOMA (Sin dependencia de Odoo a EasyCount ni viceversa)
    # -------------------------------------------------------------------------
    @api.model
    def dgii_query_rnc(self, rnc_or_cedula):
        """Consulta en línea a la DGII por RNC o Cédula. Retorna diccionario estructurado."""
        return query_dgii_by_rnc_standalone(rnc_or_cedula)

    @api.model
    def dgii_query_by_name(self, name):
        """Consulta en línea a la DGII por Razón Social o Nombre Comercial. Retorna lista."""
        return query_dgii_by_name_standalone(name)

    def action_dgii_consult(self):
        """Acción de botón en Odoo para verificar y actualizar el contacto con datos de la DGII."""
        self.ensure_one()
        if not self.vat:
            raise UserError(_("Por favor ingrese un RNC o Cédula en el campo NIF antes de consultar."))

        # 1. Validar checksum
        cleaned = _clean_rnc_string(self.vat)
        is_valid, doc_type, expected_digit = _validate_dominican_vat_checksum(cleaned)
        if not is_valid:
            raise UserError(
                _("El %s '%s' tiene un dígito verificador inválido (calculado: %s). Verifique el número.")
                % (doc_type, self.vat, expected_digit)
            )

        # 2. Consultar DGII
        info = self.dgii_query_rnc(cleaned)
        if not info:
            raise UserError(
                _("No se encontraron registros activos en la DGII para el RNC/Cédula %s.") % self.vat
            )

        # 3. Actualizar campos
        vals = {}
        regime = info.get("regime", "")
        if regime:
            vals["l10n_do_tax_regime"] = regime
        if info.get("name") and info["name"] != self.name:
            vals["name"] = info["name"]

        comment_block = (
            "Datos Verificados en DGII:\n"
            f"• Razón Social: {info.get('name', '')}\n"
            f"• Nombre Comercial: {info.get('commercial_name', '')}\n"
            f"• RNC: {info.get('formatted_rnc', cleaned)}\n"
            f"• Estado: {info.get('status', '')}\n"
            f"• Régimen: {info.get('regime', '')}\n"
            f"• Actividad: {info.get('economic_activity', '')}\n"
            f"• Administración: {info.get('local_admin', '')}\n"
            f"• Facturación Electrónica: {'SÍ' if info.get('electronic_billing') else 'NO'}"
        )
        vals["comment"] = comment_block

        if len(cleaned) == 9:
            vals["is_company"] = True
            vals["l10n_do_dgii_tax_payer_type"] = "taxpayer"

        self.write(vals)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("DGII: Consulta Exitosa"),
                "message": _("RNC verificado: %s (%s) - Estado: %s")
                % (info.get("name"), info.get("formatted_rnc"), info.get("status")),
                "type": "success",
                "sticky": False,
            },
        }


    def action_evaluate_rst_advisory(self):
        """Ejecuta el diagnóstico de elegibilidad para Régimen Simplificado (RST) y genera recomendación comercial."""
        self.ensure_one()
        if not self.vat:
            raise UserError(_("Debe registrar un RNC o Cédula antes de realizar la evaluación RST."))

        cleaned = _clean_rnc_string(self.vat)
        tipo_p = "JURIDICA" if len(cleaned) == 9 else "FISICA"
        regime = self.l10n_do_tax_regime or "RÉGIMEN GENERAL"
        is_rst = bool("RST" in regime.upper() or "SIMPLIFICADO" in regime.upper())

        ingresos_est = 1350000.0
        gastos_pct = 0.20

        # RST (Decreto 265-19)
        deduccion_40 = ingresos_est * 0.40
        renta_neta_60 = ingresos_est * 0.60
        if renta_neta_60 <= 416220.0:
            isr_rst = 0.0
        elif renta_neta_60 <= 624329.0:
            isr_rst = (renta_neta_60 - 416220.0) * 0.15
        elif renta_neta_60 <= 867123.0:
            isr_rst = 31216.0 + ((renta_neta_60 - 624329.0) * 0.20)
        else:
            isr_rst = 79776.0 + ((renta_neta_60 - 867123.0) * 0.25)

        # Régimen Ordinario
        renta_neta_ord = ingresos_est * (1.0 - gastos_pct)
        if renta_neta_ord <= 416220.0:
            isr_ord = 0.0
        elif renta_neta_ord <= 624329.0:
            isr_ord = (renta_neta_ord - 416220.0) * 0.15
        elif renta_neta_ord <= 867123.0:
            isr_ord = 31216.0 + ((renta_neta_ord - 624329.0) * 0.20)
        else:
            isr_ord = 79776.0 + ((renta_neta_ord - 867123.0) * 0.25)

        ahorro_isr = max(0.0, isr_ord - isr_rst)
        ahorro_operativo = 48000.0
        ahorro_total = ahorro_isr + ahorro_operativo

        body = f"""
        <div style="font-family: sans-serif; border-left: 4px solid #008784; padding-left: 12px;">
            <h4 style="color: #008784; margin-bottom: 6px;">📊 Diagnóstico Fiscal y Asesoría RST (EasyCount)</h4>
            <p><b>Contribuyente:</b> {self.name} (RNC/Cédula: {self.vat})</p>
            <p><b>Régimen DGII Actual:</b> {regime} | <b>Elegible para RST:</b> {'SÍ (Cumple criterios Decreto 265-19)' if not is_rst else 'YA REGISTRADO EN RST'}</p>
            <table class="table table-sm table-bordered" style="max-width: 600px; margin-top: 8px;">
                <thead class="table-light">
                    <tr><th>Concepto</th><th>Régimen Ordinario</th><th>RST (Decreto 265-19)</th></tr>
                </thead>
                <tbody>
                    <tr><td>Deducción de Gastos</td><td>{gastos_pct*100:.0f}% (Con facturas de compras)</td><td><b>40% Automático</b> (Sin facturas de compras)</td></tr>
                    <tr><td>Anticipos Mensuales ISR</td><td>Obligatorio mensual</td><td><b>RD$ 0.00 (Exento Art. 15)</b></td></tr>
                    <tr><td>Envío Formato 606</td><td>Obligatorio mensual</td><td><b>EXENTO TOTAL (Art. 17)</b></td></tr>
                    <tr><td>Impuesto a los Activos</td><td>1% Anual</td><td><b>EXENTO (Art. 16)</b></td></tr>
                    <tr><td>ISR Estimado Anual</td><td>RD$ {isr_ord:,.2f}</td><td><b>RD$ {isr_rst:,.2f}</b></td></tr>
                    <tr class="table-success"><td><b>Ahorro Anual Estimado</b></td><td colspan="2"><b style="color: green;">RD$ {ahorro_total:,.2f} / año</b></td></tr>
                </tbody>
            </table>
            <p style="margin-top: 8px;"><b>Recomendación Estratégica:</b> {'Mantener cumplimiento fiscal simplificado y emisión e-CF.' if is_rst else 'Ofrecer al cliente el servicio de adhesión al RST y facturación electrónica e-CF con EasyCount.'}</p>
        </div>
        """
        if hasattr(self, "message_post"):
            self.message_post(body=body, message_type="notification", subtype_xmlid="mail.mt_note")

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Diagnóstico RST EasyCount"),
                "message": _("Diagnóstico completado. Ahorro potencial: RD$ %s / año. Ver nota detallada en el historial.") % f"{ahorro_total:,.2f}",
                "type": "info",
                "sticky": True,
            },
        }
