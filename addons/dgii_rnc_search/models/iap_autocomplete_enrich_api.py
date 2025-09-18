# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

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

from ..helpers.dgii_helper import dgii_name

class ResPartner(models.Model):
    _inherit = 'res.partner'


    @api.model
    def _iap_replace_name(self, iap_data):
        if iap_data.get('name', False):
            iap_data['name'] = iap_data.get('name')

        return iap_data


    @api.model
    def _format_data_company(self, iap_data):
        super()._format_data_company(iap_data)
        self._iap_replace_name(iap_data)

        return iap_data


    from odoo import models, fields, api

    @api.onchange("vat")
    def _onchange_vat(self):
        """Cuando cambie el RNC/Cédula (vat) y tenga 7 o 9 dígitos,
        se llama al método dgii_name(None, vat)."""
        if self.vat:
            vat_clean = self.vat.replace("-", "").strip()  # quitar guiones y espacios
            if len(vat_clean) in (7, 9) and vat_clean.isdigit():
                # Llamamos a tu método
                resp = dgii_name(None, vat_clean)
                results = {
                    "data": [
                        {
                            "city": False,
                            "duns": (rec.get("rnc", "") or "").replace("-", ""),
                            "name": rec.get("name", False),
                            "country_code": "DO",
                        }
                        for rec in resp
                        if not (str(rec.get("name", "")).isdigit())
                    ]
                }
                self.name =  next((rec.get("name") for rec in results.get("data", []) if rec.get("duns") == vat_clean), None)



class IapAutocompleteEnrichAPIInherit(models.AbstractModel):
    _inherit = 'iap.autocomplete.api'


    @api.model
    def _request_partner_autocomplete(self, action, params, timeout=15):
        """ Contact endpoint to get autocomplete data.

        :return tuple: results, error code
        """


        try:
            value = params.get('query', False) or params.get('duns', "")
            is_number = value.replace("-", "").strip().isdigit()

            if is_number:
                if len(value) < 9:
                    return {'data': []} , False
                rnc = value.replace("-", "").strip()
                resp = dgii_name(term=None, rnc=rnc)

            else:
                resp = dgii_name(term=value, by="razon")



            results = {
                "data": [
                    {
                        "city": False,
                        "duns": (rec.get("rnc", "") or "").replace("-", ""),
                        "name": rec.get("name", False),
                        "country_code": "DO",
                    }
                    for rec in resp
                    if not (str(rec.get("name", "")).isdigit())
                ]
            }



            if 'enrich_' in action:
                company =  next((rec.get("name") for rec in results.get("data", []) if rec.get("duns") == params.get('duns', False)), None)
                return {'request_code': 200, 'total_cost': 1000, 'credit_error': False, 'data': {'vat': params.get('duns', False), 'name': company, 'country_code': 'DO'}}, False


        except exceptions.ValidationError:
            return False, 'Insufficient Credit'
        except (ConnectionError, HTTPError, exceptions.AccessError, exceptions.UserError) as exception:
            _logger.warning('Autocomplete API error: %s', str(exception))
            return False, str(exception)
        except iap_tools.InsufficientCreditError as exception:
            _logger.warning('Insufficient Credits for Autocomplete Service: %s', str(exception))
            return False, 'Insufficient Credit'
        except ValueError:
            return False, 'No account token'
        return results, False

