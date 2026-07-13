from odoo import fields, models, _


class GicaSepaAddAllReadyWizard(models.TransientModel):
    _name = "gica.sepa.add.all.ready.wizard"
    _description = "Add All Ready Payments"

    envelope_id = fields.Many2one(
        "gica.sepa.payment.envelope",
        required=True,
    )

    def action_add(self):
        self.ensure_one()

        envelope = self.envelope_id

        if envelope.state != "draft":
            message = "You can only add payment lines to a draft envelope."
            self.env["gica.sepa.move.info"]._gica_error(message)

        if envelope.line_ids:
            message = "This envelope already contains payment lines. Use Select Ready Payments to add a group, or remove the existing lines first."
            self.env["gica.sepa.move.info"]._gica_error(message)

        infos = self.env["gica.sepa.move.info"].search([
            ("ready", "=", True),
            ("blocked", "=", False),
            ("company_id", "=", envelope.company_id.id),
        ])

        for info in infos:
            available_amount = info._get_envelope_available_amount()

            if available_amount <= 0:
                continue

            envelope._add_move_info_line(info, payment_amount=available_amount)

        return {"type": "ir.actions.act_window_close"}