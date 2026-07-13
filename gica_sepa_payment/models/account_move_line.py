# -*- coding: utf-8 -*-

from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    gica_sepa_info_ids = fields.One2many(
        "gica.sepa.move.info",
        "move_line_id",
        string="GICA SEPA Info",
    )

    gica_sepa_payment_reference = fields.Char(
        related="move_id.payment_reference",
        string="Payment Reference",
        readonly=True,
    )

    gica_sepa_partner_bank_id = fields.Many2one(
        related="move_id.partner_bank_id",
        string="Recipient Bank",
        readonly=True,
    )

    def action_gica_prepare_sepa_payment_line(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": "Prepare SEPA Payment",
            "res_model": "gica.sepa.prepare.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_move_line_id": self.id,
            },
        }