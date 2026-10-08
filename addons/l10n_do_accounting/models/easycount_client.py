"""Cliente HTTP de EasyCount para la localizacion dominicana (sin dependencias de Odoo).

Etapa 1: autenticacion por token Bearer. `auth_mode="oauth2"` queda reservado
para la etapa 2 (client_credentials + callback administrados por cliente).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

API_PREFIX = "/odoo/v1"
AUTH_TOKEN = "token"
AUTH_OAUTH2 = "oauth2"


class EasyCountError(Exception):
    def __init__(self, message: str, status: int | None = None, detail: Any = None):
        super().__init__(message)
        self.status = status
        self.detail = detail


class EasyCountClient:
    def __init__(self, base_url: str, token: str, *, auth_mode: str = AUTH_TOKEN, timeout: float = 30.0, opener=None):
        if not base_url:
            raise EasyCountError("Falta la URL del servidor EasyCount")
        if auth_mode == AUTH_OAUTH2:
            raise EasyCountError("OAuth 2.0 aun no esta habilitado en EasyCount (etapa 2); use token")
        if not token:
            raise EasyCountError("Falta el token de EasyCount")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self._open = opener or urllib.request.urlopen

    def _request(self, method: str, path: str, body: dict | None = None) -> dict[str, Any]:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            f"{self.base_url}{API_PREFIX}{path}", data=data, method=method,
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with self._open(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode() or "{}")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode(errors="replace")
            try:
                detail = json.loads(raw).get("detail", raw)
            except ValueError:
                detail = raw
            raise EasyCountError(f"EasyCount respondio {exc.code}: {detail}", exc.code, detail) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise EasyCountError(f"No se pudo conectar con EasyCount: {exc}") from exc

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def allocate_encf(self, e_cf_type: str) -> str:
        return self._request("POST", "/encf/allocate", {"eCfType": e_cf_type})["encf"]

    def issue(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/invoices/issue", payload)

    def status(self, encf: str) -> dict[str, Any]:
        return self._request("GET", f"/invoices/{encf}/status")

    def get_credentials(self) -> dict[str, Any]:
        """Public status of the company's DGII credentials in EasyCount (never the secrets)."""
        return self._request("GET", "/credentials")

    def upload_credentials(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Certificate (.p12 base64) + its password + certification-portal password; EasyCount stores them encrypted."""
        return self._request("POST", "/credentials", payload)
