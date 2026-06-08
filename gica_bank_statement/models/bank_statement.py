from odoo import models, fields, api, _
from odoo.exceptions import UserError


class GicaBankStatement(models.Model):
    _name = 'gica.bank.statement'
    _inherit = ['gica.translation.mixin']
    _description = 'GICA Bank Statement'

    name = fields.Char(string='Statement No', required=True)

    journal_id = fields.Many2one(
        'account.journal',
        string='Bank Journal',
        required=True,
        domain=[('type', '=', 'bank')]
    )

    date = fields.Date(
        string='Statement Date',
        required=True,
        default=fields.Date.context_today
    )

    balance_start = fields.Monetary(
        string='Opening Balance',
        required=True
    )

    balance_end = fields.Monetary(
        string='Entered Closing Balance'
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='journal_id.currency_id',
        string='Currency',
        readonly=True
    )

    line_ids = fields.One2many(
        'gica.bank.statement.line',
        'statement_id',
        string='Lines'
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('validated', 'Validated'),
    ], string='Statut', default='draft', required=True)

    odoo_move_id = fields.Many2one(
        'account.move',
        string='Journal Entry',
        readonly=True
    )

    total_debit = fields.Monetary(
        string='Total Debit',
        compute='_compute_totals',
        store=True
    )

    total_credit = fields.Monetary(
        string='Total Credit',
        compute='_compute_totals',
        store=True
    )

    balance_computed = fields.Monetary(
        string='Computed Balance',
        compute='_compute_totals',
        store=True
    )

    balance_difference = fields.Monetary(
        string='Difference',
        compute='_compute_totals',
        store=True
    )

    @api.depends(
        'balance_start',
        'balance_end',
        'line_ids.amount'
    )

    def _compute_totals(self):

        for rec in self:

            total_debit = sum(
                -line.amount
                for line in rec.line_ids
                if line.amount < 0
            )

            total_credit = sum(
                line.amount
                for line in rec.line_ids
                if line.amount > 0
            )

            rec.total_debit = total_debit
            rec.total_credit = total_credit

            rec.balance_computed = (
                rec.balance_start
                + sum(rec.line_ids.mapped('amount'))
            )

            rec.balance_difference = (
                rec.balance_end
                - rec.balance_computed
            )

    def action_open_items_wizard(self):

        self.ensure_one()

        return {
            'name': _('Open Documents'),
            'type': 'ir.actions.act_window',
            'res_model': 'gica.open.items.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_statement_id': self.id,
            },
        }

    def _create_odoo_move(self):

        for rec in self:

            if rec.odoo_move_id:
                rec._gica_error(
                    "An Odoo journal entry already exists."
                )

            move_lines = []

            total_amount = 0.0

            #
            # Lignes contreparties
            #

            for line in rec.line_ids:

                amount = line.amount
                total_amount += amount

                #
                # Compte
                #

                if line.partner_id and line.move_line_id:

                    account = line.move_line_id.account_id

                elif line.account_id:

                    account = line.account_id

                else:
                    rec._gica_error(
                        "Unable to determine the account."
                    )

                #
                # Label
                #

                label = line.label

                if line.move_line_id:
                    label = (
                        line.move_line_id.move_id.name
                        or line.label
                    )

                #
                # Debit / Credit
                #

                debit = 0.0
                credit = 0.0

                if amount > 0:
                    credit = amount
                else:
                    debit = -amount

                move_lines.append((0, 0, {
                    'name': label,
                    'account_id': account.id,
                    'partner_id': line.partner_id.id or False,
                    'debit': debit,
                    'credit': credit,
                }))

            #
            # Ligne banque
            #

            bank_debit = 0.0
            bank_credit = 0.0

            if total_amount > 0:
                bank_debit = total_amount
            else:
                bank_credit = -total_amount

            move_lines.append((0, 0, {
                'name': rec.name,
                'account_id': rec.journal_id.default_account_id.id,
                'debit': bank_debit,
                'credit': bank_credit,
            }))

            #
            # Piece comptable
            #

            move = self.env['account.move'].create({
                'move_type': 'entry',
                'journal_id': rec.journal_id.id,
                'date': rec.date,
                'ref': rec.name,
                'line_ids': move_lines,
            })

            move.action_post()

            #
            # Lettrage automatique des documents selectionnes
            #

            for gica_line in rec.line_ids:

                if not gica_line.move_line_id:
                    continue

                source_line = gica_line.move_line_id

                counterpart_lines = move.line_ids.filtered(
                    lambda ml:
                        ml.account_id == source_line.account_id
                        and ml.partner_id == source_line.partner_id
                        and not ml.reconciled
                        and abs(ml.balance + gica_line.amount) < 0.0001
                )

                if counterpart_lines:
                    (source_line + counterpart_lines[0]).reconcile()

            rec.odoo_move_id = move.id

    def action_validate(self):

        for rec in self:

            if abs(rec.balance_difference) > 0.0001:
                message = "The closing balance does not match."
                rec._gica_error(message)

            rec._create_odoo_move()
            rec.state = 'validated'

    @api.onchange('journal_id')
    def _onchange_journal_id(self):

        for rec in self:

            if not rec.journal_id:
                rec.balance_start = 0.0
                continue

            domain = [
                ('journal_id', '=', rec.journal_id.id),
                ('state', '=', 'validated'),
            ]

            if rec.id and isinstance(rec.id, int):
                domain.append(('id', '!=', rec.id))

            last_statement = self.search(
                domain,
                order='date desc, id desc',
                limit=1
            )

            rec.balance_start = last_statement.balance_end if last_statement else 0.0
