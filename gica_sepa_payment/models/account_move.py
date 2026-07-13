# -*- coding: utf-8 -*-

from odoo import fields, models, _


class AccountMove(models.Model):
    _inherit = "account.move"

    gica_sepa_move_info_id = fields.Many2one(
        "gica.sepa.move.info",
        string="GICA SEPA Payment Info",
        compute="_compute_gica_sepa_move_info_id",
    )

    gica_sepa_can_prepare = fields.Boolean(
        string="Can Prepare GICA SEPA",
        compute="_compute_gica_sepa_can_prepare",
    )

    def _get_gica_supplier_move_line(self):
        self.ensure_one()
        return self.line_ids.filtered(
            lambda line:
                line.account_id.account_type == "liability_payable"
                and line.partner_id
                and not line.reconciled
        )[:1]

    def _compute_gica_sepa_move_info_id(self):
        info_model = self.env["gica.sepa.move.info"]
        for move in self:
            supplier_line = move._get_gica_supplier_move_line()
            move.gica_sepa_move_info_id = False
            if supplier_line:
                move.gica_sepa_move_info_id = info_model.search(
                    [("move_line_id", "=", supplier_line.id)],
                    limit=1,
                )

    def _compute_gica_sepa_can_prepare(self):
        for move in self:
            move.gica_sepa_can_prepare = (
                move.move_type in ("in_invoice", "in_refund")
                and move.state == "posted"
                and move.payment_state not in ("paid", "reversed")
                and bool(move._get_gica_supplier_move_line())
            )

    def action_gica_prepare_sepa_payment(self):
        self.ensure_one()

        supplier_line = self._get_gica_supplier_move_line()
        if not supplier_line:
            message = "No open supplier accounting line was found for this vendor bill."
            self.env["gica.sepa.move.info"]._gica_error(message)

        return {
            "type": "ir.actions.act_window",
            "name": _("Prepare SEPA Payment"),
            "res_model": "gica.sepa.prepare.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_move_line_id": supplier_line.id,
            },
        }