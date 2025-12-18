from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    enable_local_printing = fields.Boolean(
        string="Activar Impresión Local",
        help=(
            "Habilita la comunicación con el agente de impresión local para impresiones directas. "
            "El valor por defecto se toma de los ajustes generales."
        ),
        default=lambda self: self._get_default_enable_local_printing(),
    )
    local_printer_name = fields.Char(
        string="Nombre de la Impresora Local",
        help=(
            "Nombre de la impresora en el sistema operativo del cliente (por ejemplo, "
            '"EPSON TM-T20II"), tomado de los ajustes generales.'
        ),
        default=lambda self: self._get_default_local_printer_name(),
    )

    # URL del agente HTTP local (por defecto http://127.0.0.1:9060)
    agent_url = fields.Char(
        string="URL del Agente Local",
        help="Dirección base del agente local (ej.: http://127.0.0.1:9060)",
        default=lambda self: self._get_default_agent_url(),
    )

    # Token eliminado: conexión sin Authorization

    @api.model
    def _get_default_enable_local_printing(self):
        param_value = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("pos_any_printer_local.pos_enable_local_printing", "False")
        )
        return param_value in ("True", "1", True)

    @api.model
    def _get_default_local_printer_name(self):
        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("pos_any_printer_local.pos_local_printer_name", "")
        )

    @api.model
    def _get_default_agent_url(self):
        return (
            self.env["ir.config_parameter"].sudo().get_param(
                "pos_any_printer_local.pos_agent_url", "http://127.0.0.1:9060"
            )
        )

    @api.model
    def _get_default_agent_token(self):
        return ""

    def _loader_params_pos_config(self):
        params = super()._loader_params_pos_config()
        params["fields"].extend([
            "enable_local_printing",
            "local_printer_name",
            "agent_url",
            # token eliminado
        ])
        return params


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_enable_local_printing = fields.Boolean(
        string="Habilitar impresión local en TPV",
        help=(
            "Activa la impresión directa a una impresora conectada al equipo del cajero "
            "a través del agente local."
        ),
        config_parameter="pos_any_printer_local.pos_enable_local_printing",
        default=False,
    )
    pos_local_printer_name = fields.Char(
        string="Nombre predeterminado de impresora local",
        help="Se guarda como parámetro de sistema para reutilizarlo en nuevos TPV.",
        config_parameter="pos_any_printer_local.pos_local_printer_name",
        default="",
    )

    # Parámetros globales del agente local (expuestos en Ajustes)
    pos_agent_url = fields.Char(
        string="URL del agente local",
        help="Dirección base del agente (http://127.0.0.1:9060)",
        config_parameter="pos_any_printer_local.pos_agent_url",
        default="http://127.0.0.1:9060",
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        icp = self.env["ir.config_parameter"].sudo()
        res.update(
            pos_enable_local_printing=icp.get_param(
                "pos_any_printer_local.pos_enable_local_printing", "False"
            )
            in ("True", "1", True),
            pos_local_printer_name=icp.get_param(
                "pos_any_printer_local.pos_local_printer_name", ""
            ),
            pos_agent_url=icp.get_param(
                "pos_any_printer_local.pos_agent_url", "http://127.0.0.1:9060"
            ),
        )
        return res

    def set_values(self):
        super().set_values()
        icp = self.env["ir.config_parameter"].sudo()
        for record in self:
            icp.set_param(
                "pos_any_printer_local.pos_enable_local_printing",
                record.pos_enable_local_printing,
            )
            icp.set_param(
                "pos_any_printer_local.pos_local_printer_name",
                record.pos_local_printer_name or "",
            )
            icp.set_param(
                "pos_any_printer_local.pos_agent_url",
                record.pos_agent_url or "http://127.0.0.1:9060",
            )
            # token eliminado

        # También sincronizamos el valor por defecto en pos.config para futuros TPV.
        for record in self:
            self.env["pos.config"].sudo().search([]).write(
                {
                    "enable_local_printing": record.pos_enable_local_printing,
                    "local_printer_name": record.pos_local_printer_name or "",
                    "agent_url": record.pos_agent_url or "http://127.0.0.1:9060",
                }
            )
