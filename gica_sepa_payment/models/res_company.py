from odoo import fields, models

class ResCompany(models.Model):
    _inherit = "res.company"

    gica_sepa_cash_discount_account_id = fields.Many2one(
        "account.account",
        string="Cash Discount Account",
        domain="[('deprecated', '=', False)]",
    )