from odoo import models, fields, api
from odoo.exceptions import UserError


class GicaOpenItemsWizard(models.TransientModel):
    _name = 'gica.open.items.wizard'
    _description = 'GICA Open Items Wizard'

    statement_id = fields.Many2one(
        'gica.bank.statement',
        string='Statement',
        required=True
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        required=True
    )

    wizard_line_ids = fields.One2many(
        'gica.open.items.wizard.line',
        'wizard_id',
        string='Open Documents'
    )

    selected_total = fields.Monetary(
        string='Selected Total',
        compute='_compute_selected_total'
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='statement_id.currency_id',
        string='Currency',
        readonly=True
    )

    @api.depends('wizard_line_ids.selected')
    def _compute_selected_total(self):

        for rec in self:

            total = 0.0

            for line in rec.wizard_line_ids:

                if line.selected:
                    total += line.amount_residual

            rec.selected_total = total

    @api.onchange('partner_id')
    def _onchange_partner_id(self):

        self.wizard_line_ids = [(5, 0, 0)]

        if not self.partner_id:
            return

        move_lines = self.env['account.move.line'].search([
            ('partner_id', '=', self.partner_id.id),
            ('reconciled', '=', False),
            ('account_id.account_type', 'in', [
                'asset_receivable',
                'liability_payable'
            ]),
            ('parent_state', '=', 'posted'),
        ])

        lines = []

        for move_line in move_lines:

            if abs(move_line.amount_residual) < 0.0001:
                continue

            lines.append((0, 0, {
                'move_line_id': move_line.id,
            }))

        self.wizard_line_ids = lines

    def action_add_lines(self):

        for rec in self:

            selected_lines = rec.wizard_line_ids.filtered(
                lambda l: l.selected
            )

            if not selected_lines:
                raise UserError(
                    "Vous devez selectionner au moins un document."
                )

            for line in selected_lines:

                move_line = line.move_line_id

                self.env['gica.bank.statement.line'].create({
                    'statement_id': rec.statement_id.id,
                    'label': move_line.move_id.name
                             or move_line.name
                             or 'Document',
                    'partner_id': rec.partner_id.id,
                    'move_line_id': move_line.id,
                    'amount': move_line.amount_residual,
                })

        return {'type': 'ir.actions.act_window_close'}
