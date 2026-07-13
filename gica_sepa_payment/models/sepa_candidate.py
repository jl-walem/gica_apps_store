# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools, _

class GicaSepaCandidate(models.Model):
    _name = "gica.sepa.candidate"
    _description = "GICA SEPA Payment Candidate"
    _auto = False
    _order = "due_date, partner_name"

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        readonly=True,
    )

    partner_name = fields.Char(string="Supplier", readonly=True)
    move_id = fields.Many2one("account.move", string="Vendor Bill", readonly=True)
    move_line_id = fields.Many2one("account.move.line", string="Supplier Move Line", readonly=True)
    invoice_date = fields.Date(string="Invoice Date", readonly=True)
    due_date = fields.Date(string="Due Date", readonly=True)
    payment_reference = fields.Char(string="Payment Reference", readonly=True)
    partner_bank = fields.Char(string="Bank Account", readonly=True)
    invoice_total = fields.Monetary(
        string="Invoice Total",
        currency_field="currency_id",
        readonly=True,
    )

    discount_amount = fields.Monetary(
        string="Cash Discount",
        currency_field="currency_id",
        readonly=True,
    )

    amount_to_pay = fields.Monetary(
        string="To Pay",
        currency_field="currency_id",
        readonly=True,
    )

    amount_residual = fields.Monetary(
        string="Residual Amount",
        currency_field="currency_id",
        readonly=True,
    )

    currency_id = fields.Many2one("res.currency", readonly=True)

    move_info_id = fields.Many2one(
        "gica.sepa.move.info",
        string="Preparation",
        compute="_compute_move_info",
    )

    prepared_amount = fields.Monetary(
        string="Prepared Amount",
        currency_field="currency_id",
        compute="_compute_move_info",
    )

    preparation_ready = fields.Boolean(
        string="Ready",
        compute="_compute_move_info",
    )

    
    prepare_status = fields.Selection(
        [
            ("new", "New"),
            ("draft", "In Progress"),
            ("ready", "Ready"),
            ("blocked", "Litigation"),
        ],
        string="Preparation Status",
        compute="_compute_prepare_status",
        search="_search_prepare_status",
    )

    @api.depends("move_id")
    def _compute_prepare_status(self):
        MoveInfo = self.env["gica.sepa.move.info"]

        for rec in self:
            info = MoveInfo.search([("move_id", "=", rec.move_id.id)], limit=1)

            if not info:
                rec.prepare_status = "new"
            elif info.blocked:
                rec.prepare_status = "blocked"
            elif info.ready:
                rec.prepare_status = "ready"
            else:
                rec.prepare_status = "draft"

    def _search_prepare_status(self, operator, value):
        MoveInfo = self.env["gica.sepa.move.info"]

        if operator not in ("=", "!="):
            return []

        infos = MoveInfo.search([])

        prepared_move_ids = infos.mapped("move_id").ids
        blocked_move_ids = infos.filtered(lambda i: i.blocked).mapped("move_id").ids
        ready_move_ids = infos.filtered(lambda i: i.ready and not i.blocked).mapped("move_id").ids
        draft_move_ids = infos.filtered(lambda i: not i.ready and not i.blocked).mapped("move_id").ids

        if value == "new":
            domain = [("move_id", "not in", prepared_move_ids)]
        elif value == "blocked":
            domain = [("move_id", "in", blocked_move_ids)]
        elif value == "draft":
            domain = [("move_id", "in", draft_move_ids)]
        elif value == "ready":
            domain = [("move_id", "in", ready_move_ids)]
        else:
            domain = []

        if operator == "!=":
            domain = ["!"] + domain

        return domain
    
    def _compute_move_info(self):
        MoveInfo = self.env["gica.sepa.move.info"]

        for rec in self:
            info = MoveInfo.search([("move_id", "=", rec.move_id.id)], limit=1)

            rec.move_info_id = info
            rec.prepared_amount = info.prepared_amount if info else 0.0
            rec.preparation_ready = info.ready if info else False

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW gica_sepa_candidate AS (
                SELECT
                    aml.id AS id,
                    aml.company_id AS company_id,
                    rp.name AS partner_name,
                    am.id AS move_id,
                    aml.id AS move_line_id,
                    am.invoice_date AS invoice_date,
                    aml.date_maturity AS due_date,
                    am.payment_reference AS payment_reference,
                    rpb.acc_number AS partner_bank,
                    am.amount_total AS invoice_total,
                    ABS(aml.amount_residual) AS amount_residual,
                    COALESCE(gsmi.discount_amount, 0.0) AS discount_amount,
                    GREATEST(
                        ABS(aml.amount_residual)
                        - COALESCE(gsmi.discount_amount, 0.0)
                        - COALESCE(env.total_envelope_amount, 0.0),
                        0.0
                    ) AS amount_to_pay,
                    aml.company_currency_id AS currency_id
                FROM account_move_line aml
                JOIN account_move am ON am.id = aml.move_id
                JOIN account_account aa ON aa.id = aml.account_id
                JOIN res_partner rp ON rp.id = aml.partner_id
                LEFT JOIN res_partner_bank rpb ON rpb.id = am.partner_bank_id
                LEFT JOIN gica_sepa_move_info gsmi ON gsmi.move_line_id = aml.id
                LEFT JOIN (
                    SELECT
                        move_info_id,
                        SUM(payment_amount) AS total_envelope_amount
                    FROM gica_sepa_payment_envelope_line
                    GROUP BY move_info_id
                ) env ON env.move_info_id = gsmi.id
                WHERE aa.account_type = 'liability_payable'
                AND aml.partner_id IS NOT NULL
                AND aml.reconciled IS FALSE
                AND am.state = 'posted'
                AND am.move_type = 'in_invoice'
                AND aml.amount_residual < 0
                AND am.currency_id = (
                    SELECT id FROM res_currency WHERE name = 'EUR' LIMIT 1
                )
                AND GREATEST(
                    ABS(aml.amount_residual)
                    - COALESCE(gsmi.discount_amount, 0.0)
                    - COALESCE(env.total_envelope_amount, 0.0),
                    0.0
                ) > 0
            )
        """)

    def action_prepare_sepa(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": "Prepare SEPA Payment",
            "res_model": "gica.sepa.prepare.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_move_line_id": self.move_line_id.id,
            },
        }
    
    def action_open_pdf(self):
        self.ensure_one()
        attachment = self.env["ir.attachment"].search([
            ("res_model", "=", "account.move"),
            ("res_id", "=", self.move_id.id),
            ("mimetype", "=", "application/pdf"),
        ], limit=1)

        if not attachment:
            message = "No PDF attachment found for this invoice."
            self.env["gica.sepa.move.info"]._gica_error(message)

        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=false",
            "target": "new",
        }