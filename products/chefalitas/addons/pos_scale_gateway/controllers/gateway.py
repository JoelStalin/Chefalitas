import json

from odoo import http
from odoo.exceptions import AccessError, ValidationError
from odoo.http import request


class ScaleGatewayController(http.Controller):
    @staticmethod
    def _payload():
        if len(request.httprequest.data) > 2048:
            raise ValueError("Payload too large")
        value = json.loads(request.httprequest.data or b"{}")
        if not isinstance(value, dict):
            raise ValueError("Expected JSON object")
        return value

    @http.route("/pos_scale_gateway/pair/<int:device_id>", type="http", auth="public",
                methods=["POST"], csrf=False)
    def pair(self, device_id):
        try:
            payload = self._payload()
            device = request.env["pos.scale.device"].sudo().browse(device_id).exists()
            token = device.exchange_pairing_code(payload.get("code")) if device else False
            if not token:
                return request.make_json_response({"ok": False, "error": "Invalid pairing code"}, status=403)
            return request.make_json_response({"ok": True, "token": token})
        except (ValueError, json.JSONDecodeError):
            return request.make_json_response({"ok": False, "error": "Invalid request"}, status=400)

    @http.route("/pos_scale_gateway/reading/<int:device_id>", type="http", auth="public",
                methods=["POST"], csrf=False)
    def reading(self, device_id):
        try:
            payload = self._payload()
            token = request.httprequest.headers.get("X-Scale-Token", "")
            device = request.env["pos.scale.device"].sudo().browse(device_id).exists()
            if not device:
                raise AccessError("Unknown device")
            reading = device.accept_reading(token, payload)
            return request.make_json_response({"ok": True, "sample_id": reading.sample_id})
        except AccessError:
            return request.make_json_response({"ok": False, "error": "Unauthorized"}, status=401)
        except (ValueError, ValidationError, json.JSONDecodeError):
            return request.make_json_response({"ok": False, "error": "Invalid reading"}, status=400)
