from odoo import _,models, fields
from odoo.exceptions import UserError

class AccountMove(models.Model):
    _inherit = "account.move"

    gica_peppol_status = fields.Selection(
        [
            ("none", "Not managed"),
            ("to_generate", "To Generate"),
            ("to_send", "To Send"),
            ("sent", "Sent"),
            ("delivered", "Delivered"),
            ("rejected", "Rejected"),
            ("error", "Error"),
        ],
        default="none",
        string="Peppol Status",
    )

    def action_post(self):
        
        res = super().action_post()

        for move in self:

            if move.move_type not in ("out_invoice", "out_refund"):
                continue

            if not move.partner_id.vat:
                continue

            existing = self.env["gica.peppol.sale"].search(
                [("move_id", "=", move.id)],
                limit=1,
            )

            if not existing:
                self.env["gica.peppol.sale"].create({
                    "name": move.name or "/",
                    "move_id": move.id,
                    "partner_id": move.partner_id.id,
                    "invoice_date": move.invoice_date,
                    "partner_vat": move.partner_id.vat,
                    "amount_total": move.amount_total,
                    "currency_id": move.currency_id.id,
                    "peppol_status": "to_generate",
                })
                move.gica_peppol_status = "to_generate"

        return res
    
    def button_draft(self):
        for move in self:
            peppol_sale = self.env["gica.peppol.sale"].search(
                [("move_id", "=", move.id)],
                limit=1,
            )

            if not peppol_sale:
                continue

            if peppol_sale.peppol_status in ("sent", "delivered"):
                message="This invoice has already been sent to Peppol. Please create a credit note instead."
                peppol_sale._gica_error(message)
                
            if peppol_sale.peppol_status in ("to_generate", "to_send", "error", "rejected"):
                peppol_sale.unlink()
                move.gica_peppol_status = "none"

        return super().button_draft()
