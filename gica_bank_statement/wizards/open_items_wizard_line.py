from odoo import models, fields


class GicaOpenItemsWizardLine(models.TransientModel):
    _name = 'gica.open.items.wizard.line'
    _description = 'GICA Open Items Wizard Line'

    wizard_id = fields.Many2one(
        'gica.open.items.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )

    selected = fields.Boolean(
        string='Selected'
    )

    move_line_id = fields.Many2one(
        'account.move.line',
        string='Document'
    )

    date = fields.Date(
        related='move_line_id.date',
        string='Date',
        readonly=True
    )

    move_name = fields.Char(
        related='move_line_id.move_name',
        string='Journal Entry',
        readonly=True
    )

    name = fields.Char(
        related='move_line_id.name',
        string='Label',
        readonly=True
    )

    amount_residual = fields.Monetary(
        related='move_line_id.amount_residual',
        string='Open Amount',
        readonly=True
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='wizard_id.currency_id',
        string='Currency',
        readonly=True
    )
