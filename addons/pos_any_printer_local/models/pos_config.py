from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    enable_local_printing = fields.Boolean(
        string="Activar Impresión Local (WebSocket)",
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

    @api.model
    def _get_default_enable_local_printing(self):
        """
        Obtiene el valor por defecto desde el parámetro de sistema.
        Se usa al crear nuevos TPVs para mantener consistencia con Ajustes.
        """
        param_value = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("pos_any_printer_local.pos_enable_local_printing", "False")
        )
        return param_value in ("True", "1", True)

    @api.model
    def _get_default_local_printer_name(self):
        """Recupera el nombre de impresora configurado en Ajustes."""
        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("pos_any_printer_local.pos_local_printer_name", "")
        )

    def _loader_params_pos_config(self):
        """Asegura que los nuevos campos estén disponibles en el frontend del POS."""
        params = super()._loader_params_pos_config()
        params["fields"].extend(["enable_local_printing", "local_printer_name"])
        return params


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Opción global para habilitar la impresión local en TPV.
    pos_enable_local_printing = fields.Boolean(
        string="Habilitar impresión local en TPV",
        help=(
            "Activa la impresión directa a una impresora conectada al equipo del cajero "
            "a través del agente local."
        ),
        config_parameter="pos_any_printer_local.pos_enable_local_printing",
        default=False,
    )
    # Nombre de la impresora local a utilizar de forma predeterminada.
    pos_local_printer_name = fields.Char(
        string="Nombre predeterminado de impresora local",
        help="Se guarda como parámetro del sistema para reutilizarlo en nuevos TPV.",
        config_parameter="pos_any_printer_local.pos_local_printer_name",
        default="",
    )

    @api.model
    def get_values(self):
        """
        Compatibilidad multi-versión: en v16+ config_parameter gestiona la
        persistencia, pero mantenemos get/set para instalaciones v15.
        """
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

        # También sincronizamos el valor por defecto en pos.config para futuros TPV.
        for record in self:
            self.env["pos.config"].sudo().search([]).write(
                {
                    "enable_local_printing": record.pos_enable_local_printing,
                    "local_printer_name": record.pos_local_printer_name or "",
                }
            )
