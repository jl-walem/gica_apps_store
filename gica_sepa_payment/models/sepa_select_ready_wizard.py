from odoo import api, fields, models

class GicaSepaSelectReadyWizard(models.TransientModel):
    _name = "gica.sepa.select.ready.wizard"
    _description = "Add Ready Payments"

    envelope_id = fields.Many2one(
        "gica.sepa.payment.envelope",
        required=True,
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Supplier",
        domain="[('id', 'in', available_partner_ids)]",
    )

    search_text = fields.Char(
        string="Search",
    )

    overdue_before = fields.Date(
        string="Overdue Before",
    )

    available_partner_ids = fields.Many2many(
        "res.partner",
        compute="_compute_available_partner_ids",
    )

    def action_add(self):
        self.ensure_one()

        domain = [
            ("ready", "=", True),
            ("blocked", "=", False),
            ("company_id", "=", self.envelope_id.company_id.id),
        ]

        if self.partner_id:
            domain.append(
                ("move_line_id.partner_id", "=", self.partner_id.id)
            )

        if self.overdue_before:
            domain.append(
                ("move_line_id.date_maturity", "<=", self.overdue_before)
            )

        if self.search_text:
            search = self.search_text.strip()
            domain += [
                "|", "|", "|",
                ("move_line_id.move_id.name", "ilike", search),
                ("move_line_id.move_id.ref", "ilike", search),
                ("move_line_id.partner_id.name", "ilike", search),
                ("payment_note", "ilike", search),
            ]

        infos = self.env["gica.sepa.move.info"].search(domain)

        for info in infos:
            available_amount = info._get_envelope_available_amount()

            if available_amount <= 0:
                continue

            self.envelope_id._add_move_info_line(
                info,
                payment_amount=available_amount,
            )

        return {
            "type": "ir.actions.act_window_close",
        }
     
    @api.depends("envelope_id")
    def _compute_available_partner_ids(self):
        for rec in self:
            if not rec.envelope_id:
                rec.available_partner_ids = False
                continue

            infos = self.env["gica.sepa.move.info"].search([
                ("ready", "=", True),
                ("blocked", "=", False),
                ("company_id", "=", rec.envelope_id.company_id.id),
            ])

            rec.available_partner_ids = infos.mapped("move_line_id.partner_id")