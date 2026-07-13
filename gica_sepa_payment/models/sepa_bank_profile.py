from odoo import api, fields, models, _

class GicaSepaBankProfile(models.Model):
    _name = "gica.sepa.bank.profile"
    _description = "SEPA Bank Profile"
    _order = "code, name"

    name = fields.Char(
        string="Name",
        required=True,
    )

    code = fields.Char(
        string="SEPA Code",
        required=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    bank_journal_id = fields.Many2one(
        "account.journal",
        string="Bank Journal",
        required=True,
        domain="[('type', '=', 'bank'), ('company_id', '=', company_id)]",
    )

    active = fields.Boolean(
        default=True,
    )

    sequence_id = fields.Many2one(
        "ir.sequence",
        string="Sequence",
        readonly=True,
        copy=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        profiles = super().create(vals_list)

        for profile in profiles:
            if not profile.sequence_id:
                profile.sequence_id = self.env["ir.sequence"].create({
                    "name": profile.code,
                    "code": "gica.sepa.payment.envelope.%s.%s" % (
                        profile.company_id.id,
                        profile.code,
                    ),
                    "prefix": "%s/%%(year)s/" % profile.code,
                    "padding": 6,
                    "company_id": profile.company_id.id,
                })

        return profiles
    
    def unlink(self):
        sequences = self.mapped("sequence_id")

        res = super().unlink()

        if sequences:
            sequences.unlink()

        return res

    def name_get(self):
        result = []
        for rec in self:
            name = rec.code
            if rec.bank_journal_id:
                name = "%s - %s" % (rec.code, rec.bank_journal_id.display_name)
            result.append((rec.id, name))
        return result
    
    def write(self, vals):
        protected_fields = {"code", "company_id", "bank_journal_id", "sequence_id"}

        if protected_fields.intersection(vals):
            for profile in self:
                envelope_count = self.env["gica.sepa.payment.envelope"].search_count([
                    ("sepa_profile_id", "=", profile.id),
                ])
                if envelope_count:
                    message = "You cannot modify this SEPA Journal because it is already used by payment envelopes."
                    self.env["gica.sepa.move.info"]._gica_error(message)

        return super().write(vals)
    
    def unlink(self):
        for profile in self:
            envelope_count = self.env["gica.sepa.payment.envelope"].search_count([
                ("sepa_profile_id", "=", profile.id),
            ])
            if envelope_count:
                message = "You cannot delete this SEPA Journal because it is already used by payment envelopes."
                self.env["gica.sepa.move.info"]._gica_error(message)

        sequences = self.mapped("sequence_id")
        res = super().unlink()

        if sequences:
            sequences.unlink()

        return res

    _sql_constraints = [
        (
            "code_company_unique",
            "unique(code, company_id)",
            "The SEPA code must be unique per company.",
        ),
        (
            "bank_journal_unique",
            "unique(bank_journal_id)",
            "A bank journal can only be linked to one SEPA bank profile.",
        ),
    ]