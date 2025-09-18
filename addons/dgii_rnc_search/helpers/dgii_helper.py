import logging
import requests

from odoo import api, models, exceptions, _, release
from odoo.addons.iap.tools import iap_tools
from requests.exceptions import HTTPError

_logger = logging.getLogger(__name__)


import json
import re
from urllib.parse import urlencode

from lxml import html

from odoo import http
from odoo.http import request

def dgii_name( term=None, rnc=None, by=None, **kw):
    """Si by == 'razon' o el término parece un nombre (no solo dígitos), consultamos por Razón Social.
    De lo contrario, consultamos por RNC/Cédula.
    """

    _logger.info("_______ searching Emy 22 AA")

    q = (rnc or term or "").strip()
    try:
        if not q:
            return []

        is_name = (by == "razon") or (not re.fullmatch(r"\d[\d\-]*", q))
        if is_name:
            results = _consultar_dgii_por_razon_social(q) or []
        else:
            data = _consultar_dgii_por_rnc(q)
            results = [data] if data else []

        payload = []
        for d in results:
            if not d:
                continue
            nombre = (d.get("nombre") or "").strip()
            nombre_comercial = (d.get("nombre_comercial") or "").strip()
            name = nombre or nombre_comercial or ""
            rnc_val = (d.get("rnc") or q).strip()
            if name or rnc_val:
                payload.append({
                    "name": name or rnc_val,
                    "rnc": rnc_val,
                    "label": u"{} - {}".format(rnc_val, (name or "")),
                })
        return payload
    except Exception as e:
        _logger.error("Error en /dgii_ws_dgii_name: %s", e, exc_info=True)
        raise e

def _get_tokens( session, URL, headers):
    r1 = session.get(URL, headers=headers, timeout=20)
    r1.raise_for_status()
    page = html.fromstring(r1.content)

    def get_xpath(page, xp):
        vals = page.xpath(xp)
        return vals[0].strip() if vals else ""

    return {
        "viewstate": get_xpath(page, "//input[@id='__VIEWSTATE']/@value"),
        "eventvalidation": get_xpath(page, "//input[@name='__EVENTVALIDATION']/@value"),
        "viewstategenerator": get_xpath(page, "//input[@name='__VIEWSTATEGENERATOR']/@value"),
    }

def _post( session, URL, data, headers):
    post_headers = headers.copy()
    post_headers.update({
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://www.dgii.gov.do",
        "Referer": URL,
    })
    r2 = session.post(URL, data=urlencode(data), headers=post_headers, timeout=30)
    r2.raise_for_status()
    return html.fromstring(r2.content)

def _consultar_dgii_por_rnc( vat):
    URL = "https://dgii.gov.do/app/WebApps/ConsultasWeb2/ConsultasWeb/consultas/rnc.aspx"
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-DO,es;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
    }

    tokens = _get_tokens(session, URL, headers)
    if not all(tokens.values()):
        _logger.warning("Tokens ASP.NET no encontrados (RNC)")
        return None

    form_data = {
        "ctl00$smMain": "ctl00$cphMain$upBusqueda|ctl00$cphMain$btnBuscarPorRNC",
        "ctl00$cphMain$txtRNCCedula": vat,
        "ctl00$cphMain$txtRazonSocial": "",
        "ctl00$cphMain$hidActiveTab": "rnc",
        "__EVENTTARGET": "",
        "__EVENTARGUMENT": "",
        "__VIEWSTATE": tokens["viewstate"],
        "__VIEWSTATEGENERATOR": tokens["viewstategenerator"],
        "__EVENTVALIDATION": tokens["eventvalidation"],
        "__ASYNCPOST": "true",
        "ctl00$cphMain$btnBuscarPorRNC": "Buscar",
    }

    page = _post(session, URL, form_data, headers)
    return _parse_detalle(page, fallback_rnc=vat)

def _consultar_dgii_por_razon_social( nombre):
    """Basado en tu payload de ejemplo para BUSCAR por Razón Social."""

    _logger.info("_____ nombfe")
    _logger.info(nombre)
    URL = "https://dgii.gov.do/app/WebApps/ConsultasWeb2/ConsultasWeb/consultas/rnc.aspx"
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-DO,es;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
    }

    tokens = _get_tokens(session, URL, headers)
    # _logger.info(tokens)
    # if not all(tokens.values()):
    #     _logger.warning("Tokens ASP.NET no encontrados (Razón Social),,,")
    #     return None

    form_data = {
        "ctl00$smMain": "ctl00$cphMain$upBusqueda|ctl00$cphMain$btnBuscarPorRazonSocial",
        "ctl00$cphMain$txtRNCCedula": "",
        "ctl00$cphMain$txtRazonSocial": nombre,
        "ctl00$cphMain$hidActiveTab": "razonsocial",
        "__EVENTTARGET": "ctl00$cphMain$btnBuscarPorRazonSocial",
        "__EVENTARGUMENT": "",
        "__VIEWSTATE": tokens["viewstate"],
        "__VIEWSTATEGENERATOR": tokens["viewstategenerator"],
        "__EVENTVALIDATION": tokens["eventvalidation"],
        "__ASYNCPOST": "true",
        "ctl00$cphMain$btnBuscarPorRazonSocial": "Buscar",
    }

    page = _post(session, URL, form_data, headers)

    # 1) Intentar detalle directo (si solo hay un resultado)
    detalle = _parse_detalle(page)
    if detalle:
        return [detalle]

    # 2) Intentar lista de resultados (si hay múltiples)
    results = _parse_lista(page)
    return results

# === Parsers ===

def _parse_detalle( page, fallback_rnc=None):
    """Parsea la tabla de detalle (id='ctl00_cphMain_dvDatosContribuyentes')."""
    def xv(x):
        v = page.xpath(x)
        return (v[0].strip() if v else "")

    # Buscar por id exacto
    table = page.xpath("//table[@id='ctl00_cphMain_dvDatosContribuyentes']")
    if not table:
        # A veces, por contenido
        table = page.xpath("//table[contains(@class,'detailview')]")
    if not table:
        return None

    nombre = xv("//table[contains(@id,'dvDatosContribuyentes')]//tr[2]/td[2]/text()") or \
                xv("//table[contains(@class,'detailview')]//tr[2]/td[2]/text()")
    nombre_comercial = xv("//table[contains(@id,'dvDatosContribuyentes')]//tr[3]/td[2]/text()") or \
                        xv("//table[contains(@class,'detailview')]//tr[3]/td[2]/text()")
    rnc = xv("//table[contains(@id,'dvDatosContribuyentes')]//tr[1]/td[2]/text()") or \
            xv("//table[contains(@class,'detailview')]//tr[1]/td[2]/text()") or (fallback_rnc or "")
    estado = xv("//table[contains(@id,'dvDatosContribuyentes')]//tr[6]/td[2]/text()") or \
                xv("//table[contains(@class,'detailview')]//tr[6]/td[2]/text()")

    if not (nombre or nombre_comercial or rnc or estado):
        return None

    # Limpiar posibles caracteres no imprimibles
    def clean(s):
        return (s or "").replace(u"\xa0", " ").strip()

    return {
        "nombre": clean(nombre),
        "nombre_comercial": clean(nombre_comercial),
        "rnc": clean(rnc),
        "estado": clean(estado),
    }

def _parse_lista( page):
    """Intenta parsear una tabla listada de resultados por nombre.
    Buscamos cualquier tabla con encabezados que contengan 'RNC' y 'Nombre'.
    """
    tables = page.xpath("//table")
    results = []

    for t in tables:
        headers = ["".join(h.xpath(".//text()")).strip().lower() for h in t.xpath(".//th")]
        if not headers:
            # algunas tablas usan la primera fila <tr> como header
            first_tr = t.xpath(".//tr[1]")
            if first_tr:
                headers = ["".join(td.xpath(".//text()")).strip().lower() for td in first_tr[0].xpath(".//td")]

        cond = any("rnc" in h or "cédula" in h or "cedula" in h for h in headers) and \
                any("nombre" in h or "razón" in h or "razon" in h for h in headers)
        if not cond:
            continue

        # Leer filas (saltando header)
        rows = t.xpath(".//tr[position()>1]")
        for r in rows:
            cols = [" ".join(td.xpath(".//text()")).strip() for td in r.xpath(".//td")]
            if len(cols) < 2:
                continue
            # Heurística: rnc en primera col, nombre en segunda
            rnc = cols[0]
            nombre = cols[1]
            if not (rnc or nombre):
                continue
            results.append({
                "rnc": rnc,
                "nombre": nombre,
                "nombre_comercial": "",
                "estado": "",
            })

        if results:
            break

    return results or None
