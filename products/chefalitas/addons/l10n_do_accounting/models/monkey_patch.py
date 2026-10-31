# from odoo import models, api

# class AccountMove(models.Model):
#     _inherit = "account.move"

#     @api.depends("posted_before", "state", "journal_id", "date", "move_type")
#     def _compute_name(self):
#         self = self.sorted(lambda m: (m.date, m.ref or "", m.id))

#         for move in self:
#             # Saltar si proviene del POS
#             if self.env.context.get("from_pos_order") or self.env.context.get("pos_session_id"):
#                 continue

#             # Saltar si se indica que no se debe generar secuencia
#             if self.env.context.get("skip_auto_sequence"):
#                 continue

#             # Saltar si el movimiento está cancelado
#             if move.state == "cancel":
#                 continue

#             move_has_name = move.name and move.name != "/"

#             if move_has_name or move.state != "posted":
#                 if not move.posted_before and not move._sequence_matches_date():
#                     if move._get_last_sequence():
#                         move.name = False
#                         continue
#                 else:
#                     if (move_has_name and move.posted_before) or (
#                         not move_has_name and move._get_last_sequence()
#                     ):
#                         continue

#             if move.date and (not move_has_name or not move._sequence_matches_date()):
#                 move._set_next_sequence()

#         self.filtered(lambda m: not m.name and not m.quick_edit_mode).name = "/"
#         self._inverse_name()

#         # Lógica NCF para República Dominicana bajo normativas DGII 2025
#         do_moves = self.filtered(lambda x: (
#             x.country_code == "DO"
#             and x.l10n_latam_use_documents
#             and x.l10n_latam_document_type_id
#             and not x.l10n_latam_manual_document_number
#             and not x.l10n_do_enable_first_sequence
#             and x.state == "posted"
#             and not x.l10n_do_fiscal_number
#         ))

#         for move in do_moves:
#             # El contexto asegura que se tome la secuencia fiscal
#             move.with_context(is_l10n_do_seq=True)._set_next_sequence()

#             # Validación DGII 2025: No permitir que el NCF sea vacío o incorrecto
#             if not move.l10n_do_fiscal_number or move.l10n_do_fiscal_number == "/":
#                 raise ValueError(
#                     f"No se pudo generar un NCF válido para el documento {move.id}. "
#                     "Verifique la secuencia fiscal configurada para este tipo de comprobante."
#                 )

#             # Asignar el NCF como nombre final del movimiento
#             move.name = move.l10n_do_fiscal_number

#         # Procesar movimientos que no son de República Dominicana
#         non_do_moves = self.filtered(lambda m: m.country_code != "DO")
#         if non_do_moves:
#             super(AccountMove, non_do_moves)._compute_name()
