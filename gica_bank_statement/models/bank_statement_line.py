from odoo import models, fields, api, _
from odoo.exceptions import UserError
import os

class GicaBankStatementLine(models.Model):
    _name = 'gica.bank.statement.line'
    _inherit = ['gica.translation.mixin']
    _description = 'GICA Bank Statement Line'

    statement_id = fields.Many2one(
        'gica.bank.statement',
        string='Statement',
        required=True,
        ondelete='cascade'
    )

    label = fields.Char(
        string='Label',
        required=True
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Partner'
    )

    move_line_id = fields.Many2one(
        'account.move.line',
        string='Document',
        domain="[('partner_id', '=', partner_id), ('reconciled', '=', False), ('account_id.account_type', 'in', ('asset_receivable', 'liability_payable'))]"
    )

    account_id = fields.Many2one(
        'account.account',
        string='Account'
    )

    amount = fields.Monetary(
        string='Amount'
    )

    note = fields.Char(
        string='Note'
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='statement_id.currency_id',
        string='Currency',
        readonly=True
    )

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        for rec in self:
            if not rec.partner_id:
                rec.move_line_id = False
                return

            if not rec.account_id and not rec.move_line_id:
                default_account = rec._get_default_partner_account()
                if default_account:
                    rec.account_id = default_account

    @api.onchange('account_id')
    def _onchange_account_id(self):
        for rec in self:
            if rec.account_id:
                if not rec._is_receivable_or_payable_account(rec.account_id):
                    rec.partner_id = False
                    rec.move_line_id = False

    @api.onchange('move_line_id')
    def _onchange_move_line_id(self):
        for rec in self:
            if rec.move_line_id:
                rec.partner_id = rec.move_line_id.partner_id
                rec.account_id = rec.move_line_id.account_id
                rec.amount = rec.move_line_id.amount_residual

    def _is_receivable_or_payable_account(self, account):
        return account.account_type in (
            'asset_receivable',
            'liability_payable'
        )

    def _get_default_partner_account(self):

        self.ensure_one()

        if not self.partner_id:
            return False

        if self.partner_id.customer_rank > 0 and self.partner_id.supplier_rank == 0:
            return self.partner_id.property_account_receivable_id

        if self.partner_id.supplier_rank > 0 and self.partner_id.customer_rank == 0:
            return self.partner_id.property_account_payable_id

        return False

    def _get_effective_account(self):

        self.ensure_one()

        if self.move_line_id:
            return self.move_line_id.account_id

        if self.account_id:
            return self.account_id

        return self._get_default_partner_account()

    @api.constrains(
        'partner_id',
        'account_id',
        'move_line_id'
    )
    def _check_partner_account(self):

        for rec in self:

            effective_account = rec._get_effective_account()

            if not effective_account:
                rec._gica_error(
                    "You must select a customer/supplier account or a document."
                )

            if rec.move_line_id and not rec.partner_id:
                rec._gica_error(
                    "A document requires a partner."
                )

            if rec.move_line_id and rec.move_line_id.partner_id != rec.partner_id:
                rec._gica_error(
                    "The selected document does not belong to the selected partner."
                )

            if rec.partner_id and rec.account_id:
                if not rec._is_receivable_or_payable_account(rec.account_id):
                    rec._gica_error(
                        "A partner is only allowed with a customer or supplier account."
                    )

            if rec.partner_id and not rec.account_id and not rec.move_line_id:
                if not rec._get_default_partner_account():
                    rec._gica_error(
                        "This partner is both customer and supplier. Please select the customer or supplier account."
                    )
