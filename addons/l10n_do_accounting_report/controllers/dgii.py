from urllib.parse import urlencode
from werkzeug.utils import redirect as werkzeug_redirect

from odoo.http import Controller, request, route


class DgiiReportsControllers(Controller):
    """Controller for DGII-related redirects and utilities."""

    @route("/test", type="http", auth="public", methods=["GET"])
    def get_hello(self) -> str:
        """Return a simple greeting for testing the endpoint."""
        return "hola amigos"

    @route("/dgii_reports", type="http", auth="user", methods=["GET"])
    def redirect_link(self, rnc: str = None, invoice_id: str = None, modify: str = None) -> werkzeug_redirect:
        """Redirect to a partner or invoice form view based on RNC or invoice ID.

        Args:
            rnc (str, optional): Partner's VAT (RNC) to search for.
            invoice_id (str, optional): ID of the invoice to redirect to.
            modify (str, optional): Flag to indicate a modifying invoice (not implemented).

        Returns:
            werkzeug_redirect: Redirect to the appropriate form view or default web page.
        """
        url = "/web"
        record = None

        if rnc:
            record = request.env["res.partner"].search([("vat", "=", rnc)], limit=1)
        elif invoice_id and not modify:
            try:
                record = request.env["account.move"].browse(int(invoice_id))
                if not record.exists():
                    record = None
            except ValueError:
                record = None
        elif invoice_id and modify:
            # TODO: Implement logic to find modifying invoice (e.g., corrective invoice)
            # Example: Search for a corrective invoice linked to invoice_id
            # record = request.env["account.move"].search([
            #     ("reversed_entry_id", "=", int(invoice_id))
            # ], limit=1)
            pass

        if record:
            # Use action reference instead of get_access_action (deprecated in Odoo 18)
            model_action_map = {
                "res.partner": "base.action_partner_form",
                "account.move": "account.action_move_out_invoice_type",
            }
            action_ref = model_action_map.get(record._name)
            if not action_ref:
                return werkzeug_redirect(url)

            url_params = {
                "model": record._name,
                "action": request.env.ref(action_ref).id,
            }

            if len(record) == 1:
                url_params["id"] = record.id
                url_params["active_id"] = record.id

            # Use form view directly (get_formview_id is deprecated)
            form_view = request.env.ref(f"{record._module}.{record._name}_view_form", False)
            if form_view:
                url_params["view_id"] = form_view.id

            url = f"/web?{urlencode(url_params)}"

        return werkzeug_redirect(url)