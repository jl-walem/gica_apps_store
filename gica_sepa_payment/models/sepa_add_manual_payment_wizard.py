from odoo import api, fields, models, _

class GicaSepaAddManualPaymentWizard(models.TransientModel):
    _name = "gica.sepa.add.manual.payment.wizard"
    _description = "Add Manual Payment"

    envelope_id = fields.Many2one(
        "gica.sepa.payment.envelope",
        required=True,
    )

    company_id = fields.Many2one(
        related="envelope_id.company_id",
        readonly=True,
    )

    currency_id = fields.Many2one(
        related="envelope_id.currency_id",
        readonly=True,
    )

    available_move_info_ids = fields.Many2many(
        "gica.sepa.move.info",
        compute="_compute_available_move_info_ids",
    )

    move_info_id = fields.Many2one(
        "gica.sepa.move.info",
        string="Document",
        required=True,
        domain="[('id', 'in', available_move_info_ids)]",
    )

    available_amount = fields.Monetary(
        string="To Pay",
        currency_field="currency_id",
        readonly=True,
    )

    payment_amount = fields.Monetary(
        string="Payment Amount",
        currency_field="currency_id",
        required=True,
    )

    @api.depends("envelope_id")
    def _compute_available_move_info_ids(self):
        MoveInfo = self.env["gica.sepa.move.info"]

        for wiz in self:
            if not wiz.envelope_id:
                wiz.available_move_info_ids = False
                continue

            used_infos = wiz.envelope_id.line_ids.mapped("move_info_id").ids

            domain = [
                ("ready", "=", True),
                ("blocked", "=", False),
                ("company_id", "=", wiz.envelope_id.company_id.id),
            ]

            if used_infos:
                domain.append(("id", "not in", used_infos))

            wiz.available_move_info_ids = MoveInfo.search(domain)

    @api.onchange("move_info_id")
    def _onchange_move_info_id(self):
        for wiz in self:
            if not wiz.move_info_id:
                wiz.available_amount = 0.0
                wiz.payment_amount = 0.0
                continue

            available = wiz.move_info_id._get_envelope_available_amount()

            wiz.available_amount = available
            wiz.payment_amount = available

    def action_add(self):
        self.ensure_one()

        if self.envelope_id.state != "draft":
            message = "You can only add payment lines to a draft envelope."
            self.env["gica.sepa.move.info"]._gica_error(message)

        if not self.move_info_id:
            message = "Please select a document."
            self.env["gica.sepa.move.info"]._gica_error(message)

        if self.move_info_id in self.envelope_id.line_ids.mapped("move_info_id"):
            message = "This document is already present in this payment envelope."
            self.env["gica.sepa.move.info"]._gica_error(message)

        available = self.move_info_id._get_envelope_available_amount()

        if available <= 0:
            message = "There is no remaining amount to pay for this document."
            self.env["gica.sepa.move.info"]._gica_error(message)

        if self.payment_amount <= 0:
            message = "Payment amount must be positive."
            self.env["gica.sepa.move.info"]._gica_error(message)

        if self.payment_amount > available:
            message = "Payment amount cannot exceed the available amount."
            self.env["gica.sepa.move.info"]._gica_error(message)

        self.envelope_id._add_move_info_line(
            self.move_info_id,
            payment_amount=self.payment_amount,
        )

        return {"type": "ir.actions.act_window_close"}