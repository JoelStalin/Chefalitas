# Migration script to copy settings from old pos_any_printer configs to new local_printer_name
# Usage: run with odoo shell or as a script with proper Odoo environment

from odoo import api, SUPERUSER_ID

def migrate(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        # Example: if old module stored default printer in ir.config_parameter 'pos_any_printer.default_printer'
        param = env['ir.config_parameter'].sudo().get_param('pos_any_printer.default_printer')
        if not param:
            print('No se encontró configuración antigua para migrar')
            return
        print('Migrando valor:', param)
        for cfg in env['pos.config'].sudo().search([]):
            if not cfg.local_printer_name:
                cfg.write({'local_printer_name': param})
                print('Escrito en pos.config', cfg.id)
    except Exception as e:
        print('Error durante migración:', e)

if __name__ == '__main__':
    print('Este script está pensado para ejecutarse en el contexto de Odoo shell o desde un entrypoint con DB abierta.')
