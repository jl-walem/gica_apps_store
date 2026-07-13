# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class GicaSepaPrepareWizard(models.TransientModel):
    _name = "gica.sepa.prepare.wizard"
    _description = "Prepare GICA SEPA Payment"
    _inherit = ["gica.sepa.translation.mixin"]

    move_line_id = fields.Many2one("account.move.line", required=True)

    move_id = fields.Many2one(related="move_line_id.move_id", readonly=True)
    partner_id = fields.Many2one(related="move_line_id.partner_id", readonly=True)
    currency_id = fields.Many2one(related="move_line_id.company_currency_id", readonly=True)
    due_date = fields.Date(related="move_line_id.date_maturity", readonly=True)

    ready = fields.Boolean(
        string="Ready",
    )

    prepared_amount = fields.Monetary(
        string="Prepared Amount",
        currency_field="currency_id",
    )

    invoice_total = fields.Monetary(
        string="Invoice Total",
        currency_field="currency_id",
        compute="_compute_payment_amounts",
    )

    amount_residual = fields.Monetary(
        string="Residual Amount",
        currency_field="currency_id",
        compute="_compute_payment_amounts",
    )

    associated_deduction_amount = fields.Monetary(
        string="Associated Deductions",
        currency_field="currency_id",
        compute="_compute_payment_amounts",
    )

    amount_to_pay = fields.Monetary(
        string="To Pay",
        currency_field="currency_id",
        compute="_compute_payment_amounts",
    )

    discount_amount = fields.Monetary(currency_field="currency_id", string="Cash Discount", default=0.0)
    discount_deadline = fields.Date()
    blocked = fields.Boolean()
    litigation_note = fields.Text()
    payment_note = fields.Text()

    associated_line_ids = fields.One2many(
        "gica.sepa.prepare.associated.line",
        "wizard_id",
        string="Associated Documents",
    )

    envelope_line_ids = fields.Many2many(
        "gica.sepa.payment.envelope.line",
        compute="_compute_envelope_lines",
        string="Payment Envelopes",
        readonly=True,
    )

    envelope_amount = fields.Monetary(
        string="In Envelopes",
        compute="_compute_envelope_lines",
        currency_field="currency_id",
        readonly=True,
    )

    @api.onchange("blocked")
    def _onchange_blocked(self):
        for wizard in self:
            if wizard.blocked:
                wizard.ready = False
                wizard.prepared_amount = 0.0

    @api.depends("move_id")
    def _compute_envelope_lines(self):
        Line = self.env["gica.sepa.payment.envelope.line"]

        for wizard in self:
            lines = Line.search([
                ("move_id", "=", wizard.move_id.id),
            ])

            wizard.envelope_line_ids = [(6, 0, lines.ids)]
            wizard.envelope_amount = sum(lines.mapped("payment_amount"))


    @api.onchange("ready")
    def _onchange_ready(self):
        for wizard in self:
            if wizard.ready and not wizard.prepared_amount:
                wizard.prepared_amount = wizard.amount_to_pay


    @api.depends(
        "move_line_id",
        "discount_amount",
        "envelope_amount",
    )
    def _compute_payment_amounts(self):
        for wizard in self:
            move_line = wizard.move_line_id

            wizard.invoice_total = move_line.move_id.amount_total if move_line else 0.0
            wizard.amount_residual = abs(move_line.amount_residual) if move_line else 0.0

            if move_line:
                partials = move_line.matched_credit_ids | move_line.matched_debit_ids
                wizard.associated_deduction_amount = sum(partial.amount for partial in partials)
            else:
                wizard.associated_deduction_amount = 0.0

            wizard.amount_to_pay = max(
                wizard.amount_residual
                - (wizard.discount_amount or 0.0)
                - (wizard.envelope_amount or 0.0),
                0.0,
            )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        

        move_line_id = (
            res.get("move_line_id")
            or self.env.context.get("default_move_line_id")
            or self.env.context.get("active_id")
        )

        if not move_line_id:
            return res

        move_line = self.env["account.move.line"].browse(move_line_id)
         # Important: needed by related/computed fields in the wizard
        res["move_line_id"] = move_line.id
        partner = move_line.partner_id.commercial_partner_id

        # Reload manual GICA-SEPA information if it already exists
        info = self.env["gica.sepa.move.info"].search([
            ("move_line_id", "=", move_line.id)
        ], limit=1)

        if info:
            res.update({
                "discount_amount": info.discount_amount,
                "discount_deadline": info.discount_deadline,
                "blocked": info.blocked,
                "litigation_note": info.litigation_note,
                "payment_note": info.payment_note,
                "ready": info.ready,
                "prepared_amount": info.prepared_amount or res.get("amount_to_pay"),
            })
        else:
            res.update({
                "ready": False,
                "prepared_amount": res.get("amount_to_pay"),
            })
            
        associated_vals = []

        # 1) Documents deja rapproches dans Odoo
        partials = move_line.matched_credit_ids | move_line.matched_debit_ids

        for partial in partials:
            if partial.credit_move_id.id == move_line.id:
                other_line = partial.debit_move_id
            else:
                other_line = partial.credit_move_id
            
            if other_line.company_id != move_line.company_id:
                continue

            associated_vals.append((0, 0, {
                "line_type": "applied",
                "move_line_id": other_line.id,
                "amount_total": abs(other_line.balance),
                "amount_used": partial.amount,
                "amount_available": abs(other_line.amount_residual),
                "amount_to_apply": 0.0,
                "currency_id": other_line.company_currency_id.id,
            }))

        # 2) NC fournisseurs et acomptes encore ouverts et disponibles
        lines = self.env["account.move.line"].search([
            ("partner_id.commercial_partner_id", "=", partner.id),
            ("id", "!=", move_line.id),
            ("company_id", "=", move_line.company_id.id),
            ("account_id.account_type", "=", "liability_payable"),
            ("move_id.state", "=", "posted"),
            ("move_id.move_type", "in", ("in_refund", "entry")),
            ("reconciled", "=", False),
            ("amount_residual", ">", 0),
        ])

        for line in lines:
            available = abs(line.amount_residual)

            associated_vals.append((0, 0, {
                "line_type": "available",
                "selected": True,
                "move_line_id": line.id,
                "amount_total": abs(line.balance),
                "amount_used": 0.0,
                "amount_available": available,
                "amount_to_apply": available,
                "currency_id": line.company_currency_id.id,
            }))

        res["associated_line_ids"] = associated_vals

        return res

    def action_create_sepa_info(self):
        self.ensure_one()

        residual = abs(self.move_line_id.amount_residual)

        if self.discount_amount < 0:
            message = "Cash discount cannot be negative."
            self.env["gica.sepa.move.info"]._gica_error(message)


        if self.discount_amount >= residual:
            message = "Cash discount must be lower than the residual amount."
            self.env["gica.sepa.move.info"]._gica_error(message)


        if self.blocked and not (self.litigation_note or "").strip():
            message = "A litigation note is required when Litigation is checked."
            self.env["gica.sepa.move.info"]._gica_error(message)


        # 1) Apply selected available credit notes as Odoo reconciliations
        for line in self.associated_line_ids.filtered(
            lambda l: l.line_type == "available"
            and l.selected
            and l.amount_to_apply > 0
        ):
            amount = line.amount_to_apply

            self.env["account.partial.reconcile"].create({
                "debit_move_id": line.move_line_id.id,
                "credit_move_id": self.move_line_id.id,
                "amount": amount,
                "debit_amount_currency": amount,
                "credit_amount_currency": amount,
            })

        # 2) Save / update GICA SEPA payment info
        existing = self.env["gica.sepa.move.info"].search([
            ("move_line_id", "=", self.move_line_id.id)
        ], limit=1)

        vals = {
            "move_line_id": self.move_line_id.id,
            "discount_amount": self.discount_amount,
            "discount_deadline": self.discount_deadline,
            "blocked": self.blocked,
            "litigation_note": self.litigation_note,
            "payment_note": self.payment_note,
            "ready": self.ready and not self.blocked,
            "prepared_amount": self.prepared_amount,
        }

        if existing:
            existing.write(vals)
            info = existing
        else:
            info = self.env["gica.sepa.move.info"].create(vals)
    
        return {
            "type": "ir.actions.act_window",
            "name": "Prepare Supplier Payments",
            "res_model": "gica.sepa.candidate",
            "view_mode": "tree",
            "target": "current",
        }
    
class GicaSepaPrepareAssociatedLine(models.TransientModel):
    _name = "gica.sepa.prepare.associated.line"
    _description = "GICA SEPA Associated Document"

    line_type = fields.Selection([
        ("applied", "Applied"),
        ("available", "Available"),
    ], string="Type", readonly=True)

    amount_total = fields.Monetary(
        string="Total",
        currency_field="currency_id",
        readonly=True,
    )

    amount_used = fields.Monetary(
        string="Used",
        currency_field="currency_id",
        readonly=True,
    )

    wizard_id = fields.Many2one(
        "gica.sepa.prepare.wizard",
        required=True,
        ondelete="cascade",
    )

    selected = fields.Boolean(string="Select")

    move_line_id = fields.Many2one(
        "account.move.line",
        string="Line123",
        readonly=True,
    )

    move_id = fields.Many2one(
        related="move_line_id.move_id",
        string="Document",
        readonly=True,
    )

    document_date = fields.Date(
        related="move_id.invoice_date",
        string="Date",
        readonly=True,
    )

    amount_available = fields.Monetary(
        string="Available",
        currency_field="currency_id",
        readonly=True,
    )

    amount_to_apply = fields.Monetary(
        string="Apply",
        currency_field="currency_id",
    )

    currency_id = fields.Many2one(
        "res.currency",
        readonly=True,
    )

    @api.constrains(
        "selected",
        "amount_to_apply",
        "amount_available",
        "line_type",
    )
    def _check_amount_to_apply(self):
        for line in self:

            if line.line_type == "applied":

                if line.selected:
                    message = "Already applied documents cannot be selected."
                    self.env["gica.sepa.move.info"]._gica_error(message)


                if line.amount_to_apply != 0:
                    message = "Amount to apply must be zero for already applied documents."
                    self.env["gica.sepa.move.info"]._gica_error(message)

                continue

            if line.line_type == "available":

                if line.amount_to_apply < 0:
                    message = "Amount to apply cannot be negative."
                    self.env["gica.sepa.move.info"]._gica_error(message)

                if line.amount_to_apply > line.amount_available:
                    message = "Amount to apply cannot exceed available amount."
                    self.env["gica.sepa.move.info"]._gica_error(message)


    
