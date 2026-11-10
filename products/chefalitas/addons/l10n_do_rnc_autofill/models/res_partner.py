import html
import logging
import re
import urllib.parse
import time
import urllib.request
from odoo import models, fields, api, _


_logger = logging.getLogger(__name__)

DGII_RNC_URL = "https://dgii.gov.do/app/WebApps/ConsultasWeb2/ConsultasWeb/consultas/rnc.aspx"
DGII_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}


_DGII_CACHE = {}


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


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    def dgii_query_rnc(self, rnc_or_cedula):
        """Consulta (solo lectura) la DGII por RNC o cedula. Cache corto para no repetir la consulta."""
        key = _clean_rnc_string(rnc_or_cedula)
        hit = _DGII_CACHE.get(key)
        if hit and time.time() - hit[0] < 600:
            return hit[1]
        res = query_dgii_by_rnc_standalone(rnc_or_cedula)
        if res:
            _DGII_CACHE[key] = (time.time(), res)
        return res

    @api.model
    def dgii_query_by_name(self, name):
        """Consulta (solo lectura) la DGII por razon social o nombre comercial. Retorna una lista."""
        return query_dgii_by_name_standalone(name)

    @api.onchange("vat")
    def _onchange_rnc_autofill_vat(self):
        clean = _clean_rnc_string(self.vat)
        if len(clean) not in (9, 11):
            return
        is_valid, doc_type, _expected = _validate_dominican_vat_checksum(clean)
        if not is_valid:
            return {
                "warning": {
                    "title": _("RNC / Cédula inválido"),
                    "message": _("El número de %s '%s' tiene un dígito verificador inválido.") % (doc_type, self.vat),
                }
            }
        info = self.dgii_query_rnc(clean)
        if info:
            self._rnc_autofill_apply(info, clean)

    @api.onchange("name")
    def _onchange_rnc_autofill_name(self):
        """Contacto nuevo escrito solo con el nombre: lo busca en la DGII y completa los datos."""
        name = (self.name or "").strip()
        if len(name) < 4 or self.vat or self._origin.id:
            return
        if name.upper() in ("CONSUMIDOR FINAL", "CLIENTE", "CLIENTE GENERAL"):
            return
        found = self.dgii_query_by_name(name)
        if not found:
            return
        if len(found) == 1:
            info = found[0]
            self.vat = info.get("rnc")
            self._rnc_autofill_apply(info, info.get("rnc"))
            return
        lines = " | ".join(
            "%s %s" % (r.get("formatted_rnc") or r.get("rnc"), r.get("name")) for r in found[:8]
        )
        return {
            "warning": {
                "title": _("Varios resultados en la DGII"),
                "message": _("Escriba el RNC del que corresponde para completar los datos: %s") % lines,
            }
        }

    def _rnc_autofill_apply(self, info, clean):
        if info.get("name"):
            self.name = info["name"]
        self.is_company = bool(info.get("is_company", len(clean or "") == 9))
        if info.get("commercial_name") and "commercial_name" in self._fields:
            self.commercial_name = info["commercial_name"]
        if info.get("regime") and "l10n_do_tax_regime" in self._fields:
            self.l10n_do_tax_regime = info["regime"]
        if "country_id" in self._fields and not self.country_id:
            do_country = self.env.ref("base.do", raise_if_not_found=False)
            if do_country:
                self.country_id = do_country
