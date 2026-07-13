# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class GicaSepaMoveInfo(models.Model):
    _name = "gica.sepa.move.info"
    _description = "GICA SEPA Supplier Payment Info"
    _inherit = ["gica.sepa.translation.mixin"]
    _order = "due_date, partner_id, id"

    move_line_id = fields.Many2one(
        "account.move.line",
        string="Supplier Move Line",
        required=True,
        ondelete="cascade",
        index=True,
    )

    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
    )

    move_id = fields.Many2one(
        related="move_line_id.move_id",
        string="Vendor Bill",
        store=True,
        readonly=True,
    )

    company_id = fields.Many2one(
        related="move_line_id.company_id",
        string="Company",
        store=True,
        readonly=True,
        index=True,
    )

    partner_id = fields.Many2one(
        related="move_line_id.partner_id",
        string="Supplier",
        store=True,
        readonly=True,
    )

    currency_id = fields.Many2one(
        related="move_line_id.company_currency_id",
        string="Currency",
        store=True,
        readonly=True,
    )

    invoice_date = fields.Date(
        related="move_id.invoice_date",
        string="Invoice Date",
        store=True,
        readonly=True,
    )

    due_date = fields.Date(
        related="move_line_id.date_maturity",
        string="Due Date",
        store=True,
        readonly=True,
    )

    amount_residual = fields.Monetary(
        related="move_line_id.amount_residual",
        string="Residual Amount",
        currency_field="currency_id",
        store=True,
        readonly=True,
    )

    discount_amount = fields.Monetary(
        string="Cash Discount",
        currency_field="currency_id",
        default=0.0,
    )

    discount_deadline = fields.Date(
        string="Discount Deadline",
    )

    deducted_amount = fields.Monetary(
        string="Deducted Amount",
        currency_field="currency_id",
        compute="_compute_deducted_amount",
        store=True,
    )

    base_amount_to_pay = fields.Monetary(
        string="Base Amount to Pay",
        currency_field="currency_id",
        compute="_compute_base_amount_to_pay",
        store=True,
    )

    litigation_note = fields.Text(
        string="Litigation Note",
    )

    payment_note = fields.Text(
        string="Payment Note",
    )

    blocked = fields.Boolean(
        string="Blocked",
    )

    ready = fields.Boolean(
        string="Ready",
        default=False,
    )

    prepared_amount = fields.Monetary(
        string="Prepared Amount",
        currency_field="currency_id",
    )

    envelope_line_ids = fields.One2many(
        "gica.sepa.payment.envelope.line",
        "move_info_id",
        string="Payment Envelopes",
        readonly=True,
    )

    @api.depends("move_line_id", "move_line_id.move_id", "move_line_id.partner_id", "prepared_amount")
    def _compute_display_name(self):
        for rec in self:
            move = rec.move_line_id.move_id
            rec.display_name = move.name or str(rec.id)

    def name_get(self):
        result = []
        for rec in self:
            move = rec.move_line_id.move_id
            name = move.name or str(rec.id)
            result.append((rec.id, name))
        return result

    @api.depends()
    def _compute_deducted_amount(self):
        for rec in self:
            rec.deducted_amount = 0.0

    @api.depends("amount_residual", "discount_amount", "deducted_amount")
    def _compute_base_amount_to_pay(self):
        for rec in self:
            rec.base_amount_to_pay = (
                rec.amount_residual
                - rec.discount_amount
                - rec.deducted_amount
            )

    def _get_envelope_available_amount(self):
        self.ensure_one()

        envelope_lines = self.env["gica.sepa.payment.envelope.line"].search([
            ("move_info_id", "=", self.id),
        ])

        total_envelopes = sum(envelope_lines.mapped("payment_amount"))

        remaining_to_pay = max(
            abs(self.base_amount_to_pay or 0.0) - total_envelopes,
            0.0,
        )

        prepared = self.prepared_amount or 0.0

        if prepared > 0:
            return min(prepared, remaining_to_pay)

        return remaining_to_pay