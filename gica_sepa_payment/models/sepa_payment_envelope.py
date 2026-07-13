from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import base64
from odoo.tools.float_utils import float_compare
from ..services.sepa_xml_generator import GicaSepaXmlGenerator

class GicaSepaPaymentEnvelope(models.Model):
    _name = "gica.sepa.payment.envelope"
    _description = "GICA SEPA Payment Envelope"
    _order = "id desc"

    name = fields.Char(default="/", required=True, copy=False)

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("posted", "Posted"),
        ],
        default="draft",
        required=True,
    )

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
         index=True,
    )

    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )

    date = fields.Date(default=fields.Date.context_today, required=True)

    account_journal_id = fields.Many2one("account.journal", string="Journal")

    account_move_id = fields.Many2one(
        "account.move",
        string="Accounting Entry",
        readonly=True,
        copy=False,
    )

    accounting_date = fields.Date(
        string="Accounting Date",
        readonly=True,
        copy=False,
    )

    line_ids = fields.One2many(
        "gica.sepa.payment.envelope.line",
        "envelope_id",
        string="Lines",
        copy=True,
    )

    total_amount = fields.Monetary(
        string="Total Amount",
        compute="_compute_total_amount",
        store=True,
    )

    line_count = fields.Integer(
        string="Number of Payments",
        compute="_compute_line_count",
    )

    sepa_profile_id = fields.Many2one(
        "gica.sepa.bank.profile",
        string="SEPA Journal",
        required=True,
        domain="[('company_id', '=', company_id)]",
        ondelete="restrict",
    )

    bank_journal_id = fields.Many2one(
        related="sepa_profile_id.bank_journal_id",
        string="Bank Journal",
        store=True,
        readonly=True,
    )

    xml_attachment_id = fields.Many2one(
        "ir.attachment",
        string="SEPA XML",
        readonly=True,
        copy=False,
    )

    xml_generated_date = fields.Datetime(
        string="XML Generated",
        readonly=True,
        copy=False,
    )

    sent_date = fields.Datetime(
        string="Sent to Bank",
        readonly=True,
        copy=False,
    )

    execution_date = fields.Date(
        string="Execution Date",
    )

    bank_execution_date = fields.Date(
        string="Executed by Bank",
        readonly=True,
        copy=False,
    )

    sent_date_display = fields.Char(
        string="Sent to Bank",
        compute="_compute_sent_date_display",
    )

    posted_date = fields.Date(
        string="Posted",
        readonly=True,
        copy=False,
    )

    account_move_name = fields.Char(
        string="Accounting Entry",
        compute="_compute_account_move_name",
        store=False,
    )


    def _compute_account_move_name(self):
        for envelope in self:
            envelope.account_move_name = envelope.account_move_id.name if envelope.account_move_id else False


    def action_open_account_move(self):
        self.ensure_one()

        if not self.account_move_id:
            message = "No accounting entry is linked to this payment envelope."
            self.env["gica.sepa.move.info"]._gica_error(message)

        return {
            "type": "ir.actions.act_window",
            "name": _("Accounting Entry"),
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.account_move_id.id,
            "target": "current",
        }

    @api.depends("sent_date")
    def _compute_sent_date_display(self):
        for rec in self:
            if rec.sent_date:
                dt = fields.Datetime.context_timestamp(rec, rec.sent_date)
                rec.sent_date_display = dt.strftime("%d/%m/%Y %H:%M")
            else:
                rec.sent_date_display = False

    def write(self, vals):
        if "line_ids" in vals:
            for rec in self:
                if rec.state != "draft":
                    message = "You can only modify lines when the envelope is in Draft state."
                    self.env["gica.sepa.move.info"]._gica_error(message)

        return super().write(vals)

    def action_generate_xml(self):
        self.ensure_one()

        if self.state != "confirmed":
            message = "You can only generate XML for a confirmed envelope."
            self.env["gica.sepa.move.info"]._gica_error(message)

        generator = GicaSepaXmlGenerator(self.env, self)
        xml_content = generator.generate()

        if self.xml_attachment_id:
            self.xml_attachment_id.unlink()

        filename = f"{self.name.replace('/', '_')}_sepa.xml"

        attachment = self.env["ir.attachment"].create({
            "name": filename,
            "type": "binary",
            "datas": base64.b64encode(xml_content),
            "res_model": self._name,
            "res_id": self.id,
            "mimetype": "application/xml",
        })

        self.xml_attachment_id = attachment.id
        self.xml_generated_date = fields.Datetime.now()

        return True
    
    def action_open_xml_attachment(self):
        self.ensure_one()

        if not self.xml_attachment_id:
            message = "No SEPA XML has been generated yet."
            self.env["gica.sepa.move.info"]._gica_error(message)

        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{self.xml_attachment_id.id}?download=true",
            "target": "self",
        }

    def action_mark_sent(self):
        self.ensure_one()

        if not self.xml_generated_date:
            message = "You must generate the XML before marking the envelope as sent."
            self.env["gica.sepa.move.info"]._gica_error(message)

        self.sent_date = fields.Datetime.now()

        return True


    def action_mark_executed(self):
        self.ensure_one()

        if not self.sent_date:
            message = "You must mark the envelope as sent before marking it as executed."
            self.env["gica.sepa.move.info"]._gica_error(message)

        self.bank_execution_date = fields.Date.context_today(self)

        return True


    def action_post_envelope(self):
        self.ensure_one()

        if not self.bank_execution_date:
            message = "You can only post an envelope after bank execution."
            self.env["gica.sepa.move.info"]._gica_error(message)

        # Comptabilisation réelle à faire plus tard
        self.posted_date = fields.Date.context_today(self)
        self.state = "posted"

        return True

    @api.depends("move_info_id.move_line_id.amount_residual_currency", "move_info_id.move_line_id.amount_residual")
    def _compute_amount_residual(self):
        for rec in self:
            line = rec.move_info_id.move_line_id
            if line:
                rec.amount_residual = abs(line.amount_residual_currency or line.amount_residual)
            else:
                rec.amount_residual = 0.0

    @api.depends("line_ids.payment_amount")
    def _compute_total_amount(self):
        for rec in self:
            rec.total_amount = sum(rec.line_ids.mapped("payment_amount"))

    @api.depends("line_ids")
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                profile_id = vals.get("sepa_profile_id")

                if profile_id:
                    profile = self.env["gica.sepa.bank.profile"].browse(profile_id)
                    if profile.sequence_id:
                        vals["name"] = profile.sequence_id.next_by_id() or "/"

        return super().create(vals_list)
    
    def action_confirm(self):
        for rec in self:
            if not rec.execution_date:
                message = "Execution date is required before confirming the payment envelope."
                self.env["gica.sepa.move.info"]._gica_error(message)

            if not rec.line_ids:
                message = "You cannot confirm an empty payment envelope."
                self.env["gica.sepa.move.info"]._gica_error(message)

            if any(line.payment_amount <= 0 for line in rec.line_ids):
                message = "All payment lines must have a positive amount."
                self.env["gica.sepa.move.info"]._gica_error(message)

            rec._consume_ready_preparations()
            rec.state = "confirmed"
    
    def action_reset_to_draft(self):
        for rec in self:
            if rec.bank_execution_date or rec.account_move_id:
                message = "You cannot reset an envelope to draft when it has been executed by the bank or posted in accounting."
                self.env["gica.sepa.move.info"]._gica_error(message)

            if rec.xml_attachment_id:
                rec.xml_attachment_id.unlink()
            
            rec._restore_ready_preparations()

            rec.write({
                "state": "draft",
                "xml_attachment_id": False,
                "xml_generated_date": False,
                "sent_date": False,
            })

    def unlink(self):
        for rec in self:
            if rec.state != "draft":
                message = "Only draft payment envelopes can be deleted."
                self.env["gica.sepa.move.info"]._gica_error(message)

        return super().unlink()

    def action_create_from_ready_candidates(self):
        message = "Please create a payment envelope manually and choose a SEPA Journal first."
        self.env["gica.sepa.move.info"]._gica_error(message)
    
    def _build_payment_communication(self, move_line, info):
        move = move_line.move_id

        if move.ref:
            return move.ref[:140]

        if move.name:
            return move.name[:140]

        return ""
    
    def _add_move_info_line(self, move_info, payment_amount=None):
        self.ensure_one()

        if self.state != "draft":
            message = "You can only add payment lines to a draft envelope."
            self.env["gica.sepa.move.info"]._gica_error(message)

        if not move_info.ready:
            message = "Only ready payment preparations can be added to an envelope."
            self.env["gica.sepa.move.info"]._gica_error(message)

        existing = self.line_ids.filtered(lambda l: l.move_info_id == move_info)
        if existing:
            return False

        amount = payment_amount
        if amount is None:
            amount = move_info._get_envelope_available_amount()

        if amount <= 0:
            return False

        communication = self._build_payment_communication(
            move_info.move_line_id,
            move_info,
        )

        return self.env["gica.sepa.payment.envelope.line"].create({
            "envelope_id": self.id,
            "move_info_id": move_info.id,
            "payment_amount": amount,
            "communication_auto": communication,
            "communication": communication,
        })
    
    def action_add_all_ready_payments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Add All Ready Payments",
            "res_model": "gica.sepa.add.all.ready.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_envelope_id": self.id,
            },
        }

    def action_select_ready_payments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Select Ready Payments",
            "res_model": "gica.sepa.select.ready.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_envelope_id": self.id,
            },
        }
    
    def action_add_manual_payment(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": _("Add Payment"),
            "res_model": "gica.sepa.add.manual.payment.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_envelope_id": self.id,
            },
        }
    
    def action_post_accounting(self):
        for envelope in self:
            envelope._check_can_post_accounting()

            move = envelope._create_accounting_move()
            move.action_post()
            envelope._reconcile_accounting_move(move)

            envelope.write({
                "account_move_id": move.id,
                "state": "posted",
                "posted_date": fields.Date.context_today(envelope),
            })

        return True
    
    def _create_accounting_move(self):
        self.ensure_one()

        company = self.company_id
        journal = self.bank_journal_id
        accounting_date = self.accounting_date or self.bank_execution_date or fields.Date.context_today(self)

        bank_account = journal.default_account_id
        if not bank_account:
            message = "The bank journal has no default account."
            self.env["gica.sepa.move.info"]._gica_error(message)

        move_lines = []

        # Fournisseurs : débit
        for line in self.line_ids:
            source_line = line.move_line_id

            move_lines.append((0, 0, {
                "name": source_line.move_id.name or self.name,
                "partner_id": source_line.partner_id.id,
                "account_id": source_line.account_id.id,
                "debit": line.payment_amount,
                "credit": 0.0,
                "currency_id": source_line.currency_id.id or company.currency_id.id,
            }))

        # Banque : crédit
        move_lines.append((0, 0, {
            "name": self.name,
            "account_id": bank_account.id,
            "debit": 0.0,
            "credit": self.total_amount,
            "currency_id": company.currency_id.id,
        }))

        move = self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": journal.id,
            "date": accounting_date,
            "ref": f"SEPA {self.name}",
            "company_id": company.id,
            "line_ids": move_lines,
        })

        return move
    
    def _reconcile_accounting_move(self, move):
        self.ensure_one()

        currency = self.company_id.currency_id

        for envelope_line in self.line_ids:
            source_line = envelope_line.move_line_id
            payment_line_name = source_line.move_id.name or self.name

            payment_lines = move.line_ids.filtered(
                lambda line:
                    line.account_id == source_line.account_id
                    and line.partner_id == source_line.partner_id
                    and line.name == payment_line_name
                    and float_compare(
                        line.debit,
                        envelope_line.payment_amount,
                        precision_rounding=currency.rounding,
                    ) == 0
                    and not line.reconciled
            )

            if not payment_lines:
                message = "No matching payment line was found for %s."
                self.env["gica.sepa.move.info"]._gica_error(
                    message,
                    source_line.move_id.name or source_line.name,
                )

            if len(payment_lines) > 1:
                message = "Several matching payment lines were found for %s."
                self.env["gica.sepa.move.info"]._gica_error(
                    message,
                    source_line.move_id.name or source_line.name,
                )

            (source_line | payment_lines).reconcile()

    def _check_can_post_accounting(self):
        self.ensure_one()

        if self.state != "confirmed":
            message = "Only confirmed envelopes can be posted."
            self.env["gica.sepa.move.info"]._gica_error(message)

        if self.account_move_id:
            message = "This envelope is already linked to an accounting entry."
            self.env["gica.sepa.move.info"]._gica_error(message)

        if not self.bank_journal_id:
            message = "No bank journal is defined on this envelope."
            self.env["gica.sepa.move.info"]._gica_error(message)

        if not self.bank_execution_date:
            message = "Bank execution date is required before posting."
            self.env["gica.sepa.move.info"]._gica_error(message)

        if not self.line_ids:
            message = "You cannot post an empty payment envelope."
            self.env["gica.sepa.move.info"]._gica_error(message)

        for line in self.line_ids:
            if not line.move_line_id:
                message = "Each envelope line must be linked to an accounting line."
                self.env["gica.sepa.move.info"]._gica_error(message)

            if line.payment_amount <= 0:
                message = "Payment amount must be positive."
                self.env["gica.sepa.move.info"]._gica_error(message)

            move_line = line.move_line_id

            if not move_line.account_id.reconcile:
                message = "The accounting line must be on a reconcilable account."
                self.env["gica.sepa.move.info"]._gica_error(message)

            if move_line.reconciled:
                message = "One of the accounting lines is already fully reconciled."
                self.env["gica.sepa.move.info"]._gica_error(message)

    def _consume_ready_preparations(self):
        for envelope in self:
            for line in envelope.line_ids:
                info = line.move_info_id
                if not info:
                    continue

                prepared = info.prepared_amount or 0.0
                amount = line.payment_amount or 0.0
                remaining = prepared - amount

                if remaining > 0:
                    info.write({
                        "ready": True,
                        "prepared_amount": remaining,
                    })
                else:
                    info.write({
                        "ready": False,
                        "prepared_amount": 0.0,
                    })

    def _restore_ready_preparations(self):
        for envelope in self:
            for line in envelope.line_ids:
                info = line.move_info_id
                if not info:
                    continue

                prepared = info.prepared_amount or 0.0
                amount = line.payment_amount or 0.0

                info.write({
                    "ready": True,
                    "prepared_amount": prepared + amount,
                })

 
class GicaSepaPaymentEnvelopeLine(models.Model):
    _name = "gica.sepa.payment.envelope.line"
    _description = "GICA SEPA Payment Envelope Line"
    _order = "id"

    envelope_id = fields.Many2one(
        "gica.sepa.payment.envelope",
        required=True,
        ondelete="cascade",
    )

    company_id = fields.Many2one(
        related="envelope_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )

    state = fields.Selection(
        related="envelope_id.state",
        store=True,
        readonly=True,
    )

    move_id = fields.Many2one(
        related="move_line_id.move_id",
        string="Invoice",
        store=True,
        readonly=True,
    )

    move_info_id = fields.Many2one(
        "gica.sepa.move.info",
        string="Document",
        required=True,
        domain="[('ready', '=', True), ('company_id', '=', company_id)]",
    )

    move_line_id = fields.Many2one(
        related="move_info_id.move_line_id",
        string="Move Line",
        store=True,
        readonly=True,
    )

    partner_id = fields.Many2one(
        related="move_info_id.move_line_id.partner_id",
        string="Supplier",
        store=True,
        readonly=True,
    )

    invoice_date = fields.Date(
        related="move_id.invoice_date",
        string="Invoice Date",
        store=True,
        readonly=True,
    )

    invoice_total = fields.Monetary(
        related="move_id.amount_total",
        string="Total",
        store=True,
        readonly=True,
    )

    date_maturity = fields.Date(
        related="move_id.invoice_date_due",
        string="Due Date",
        store=True,
        readonly=True,
    )

    currency_id = fields.Many2one(
        related="envelope_id.currency_id",
        string="Currency",
        store=True,
        readonly=True,
    )

    amount_residual = fields.Monetary(
        string="To Pay",
        compute="_compute_available_amount",
        currency_field="currency_id",
        readonly=True,
    )

    prepared_amount = fields.Monetary(
        related="move_info_id.prepared_amount",
        string="Prepared Amount",
        store=True,
        readonly=True,
    )

    payment_amount = fields.Monetary(required=True)

    communication_auto = fields.Char(
        string="Automatic Communication",
        readonly=True,
    )

    communication = fields.Char(
        string="Communication",
    )

    envelope_state = fields.Selection(
        related="envelope_id.state",
        string="State",
        readonly=True,
    )

    envelope_execution_date = fields.Date(
        related="envelope_id.execution_date",
        string="Execution Date",
        readonly=True,
    )

    envelope_line_count = fields.Integer(
        related="envelope_id.line_count",
        string="Payments",
        readonly=True,
    )

    envelope_total_amount = fields.Monetary(
        related="envelope_id.total_amount",
        string="Envelope Total",
        currency_field="currency_id",
        readonly=True,
    )

    available_move_info_ids = fields.Many2many(
        "gica.sepa.move.info",
        compute="_compute_available_move_info_ids",
    )

    available_amount = fields.Monetary(
        string="Available Amount",
        compute="_compute_available_amount",
        currency_field="currency_id",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            envelope_id = vals.get("envelope_id")
            if envelope_id:
                envelope = self.env["gica.sepa.payment.envelope"].browse(envelope_id)
                if envelope.state != "draft":
                    message = "You can only add lines when the envelope is in Draft state."
                    self.env["gica.sepa.move.info"]._gica_error(message)

        return super().create(vals_list)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            envelope_id = vals.get("envelope_id")
            if envelope_id:
                envelope = self.env["gica.sepa.payment.envelope"].browse(envelope_id)
                if envelope.state != "draft":
                    message = "You can only add lines when the envelope is in Draft state."
                    self.env["gica.sepa.move.info"]._gica_error(message)

        lines = super().create(vals_list)

        return lines

    def write(self, vals):
        for rec in self:
            if rec.envelope_id.state != "draft":
                message = "You can only modify lines when the envelope is in Draft state."
                self.env["gica.sepa.move.info"]._gica_error(message)

        return super().write(vals)


    def unlink(self):
        for rec in self:
            if rec.envelope_id.state != "draft":
                message = "You can only delete lines when the envelope is in Draft state."
                self.env["gica.sepa.move.info"]._gica_error(message)

        return super().unlink()

    def _get_available_amount_for_line(self):
        self.ensure_one()

        if not self.move_info_id:
            return 0.0

        domain = [
            ("move_info_id", "=", self.move_info_id.id),
        ]

        # Très important :
        # on exclut toute l'enveloppe courante en base,
        # car une ligne supprimée dans le formulaire peut encore exister en DB avant sauvegarde.
        if self.envelope_id and isinstance(self.envelope_id.id, int):
            domain.append(("envelope_id", "!=", self.envelope_id.id))

        if isinstance(self.id, int):
            domain.append(("id", "!=", self.id))

        other_lines = self.env["gica.sepa.payment.envelope.line"].search(domain)
        total_other_envelopes = sum(other_lines.mapped("payment_amount"))

        # On ajoute seulement les lignes encore visibles dans l'enveloppe courante.
        if self.envelope_id:
            current_lines = self.envelope_id.line_ids.filtered(
                lambda l:
                    l != self
                    and l.move_info_id == self.move_info_id
            )
            total_other_envelopes += sum(current_lines.mapped("payment_amount"))

        return max(
            abs(self.move_info_id.base_amount_to_pay or 0.0) - total_other_envelopes,
            0.0,
        )

    def _get_total_other_envelopes(self):
        self.ensure_one()

        if not self.move_info_id:
            return 0.0

        Line = self.env["gica.sepa.payment.envelope.line"]

        domain = [
            ("move_info_id", "=", self.move_info_id.id),
        ]

        if self.envelope_id and isinstance(self.envelope_id.id, int):
            domain.append(("envelope_id", "!=", self.envelope_id.id))

        if isinstance(self.id, int):
            domain.append(("id", "!=", self.id))

        other_lines_db = Line.search(domain)

        total = sum(other_lines_db.mapped("payment_amount"))

        if self.envelope_id:
            current_envelope_lines = self.envelope_id.line_ids.filtered(
                lambda l:
                    l != self
                    and l.move_info_id == self.move_info_id
            )

            total += sum(current_envelope_lines.mapped("payment_amount"))

        return total

    @api.depends(
        "move_info_id",
        "payment_amount",
        "envelope_id.line_ids",
        "envelope_id.line_ids.move_info_id",
        "envelope_id.line_ids.payment_amount",
    )
    def _compute_available_amount(self):
        for rec in self:
            available = rec._get_available_amount_for_line() if rec.move_info_id else 0.0
            rec.available_amount = available
            rec.amount_residual = available

    @api.depends(
        "envelope_id",
        "envelope_id.line_ids.move_info_id",
        "company_id",
    )
    def _compute_available_move_info_ids(self):
        MoveInfo = self.env["gica.sepa.move.info"]

        for rec in self:
            if not rec.envelope_id or not rec.company_id:
                rec.available_move_info_ids = False
                continue

            used_infos = rec.envelope_id.line_ids.filtered(
                lambda l: l != rec and l.move_info_id
            ).mapped("move_info_id").ids

            domain = [
                ("ready", "=", True),
                ("blocked", "=", False),
                ("company_id", "=", rec.company_id.id),
            ]

            if used_infos:
                domain.append(("id", "not in", used_infos))

            rec.available_move_info_ids = MoveInfo.search(domain)

    @api.onchange("move_info_id")
    def _onchange_move_info_id(self):
        for rec in self:
            info = rec.move_info_id

            rec.payment_amount = 0.0
            rec.communication_auto = False
            rec.communication = False

            if not info:
                continue

            if rec.envelope_id:
                duplicates = rec.envelope_id.line_ids.filtered(
                    lambda l: l.move_info_id == info and l != rec
                )

                if duplicates:
                    rec.move_info_id = False
                    message = "This document is already present in this payment envelope."
                    self.env["gica.sepa.move.info"]._gica_error(message)

            available = rec._get_available_amount_for_line()
            prepared = info.prepared_amount or 0.0

            rec.available_amount = available
            rec.amount_residual = available
            rec.payment_amount = min(prepared, available)

            communication = rec.envelope_id._build_payment_communication(
                info.move_line_id,
                info,
            )
            rec.communication_auto = communication
            rec.communication = communication

    @api.onchange("payment_amount", "move_info_id")
    def _onchange_payment_amount_check(self):
        for rec in self:
            if not rec.payment_amount:
                continue

            if rec.payment_amount <= 0:
                message = "Payment amount must be positive."
                self.env["gica.sepa.move.info"]._gica_error(message)


            available = rec.available_amount

            if available and rec.payment_amount > available:
                message = "Payment amount cannot exceed the available amount."
                self.env["gica.sepa.move.info"]._gica_error(message)

            
    @api.constrains("payment_amount", "move_info_id")
    def _check_payment_amount(self):
        for rec in self:
            if rec.payment_amount <= 0:
                message = "Payment amount must be positive."
                self.env["gica.sepa.move.info"]._gica_error(message)


            if not rec.move_info_id:
                continue

            total_other_envelopes = rec._get_total_other_envelopes()

            available = max(
                abs(rec.move_info_id.base_amount_to_pay or 0.0)
                - total_other_envelopes,
                0.0,
            )

            if rec.payment_amount > available:
                message = "Payment amount cannot exceed the available amount."
                self.env["gica.sepa.move.info"]._gica_error(message)
                 
    _sql_constraints = [
        (
            "envelope_move_info_unique",
            "unique(envelope_id, move_info_id)",
            "This document is already present in this payment envelope.",
        ),
    ]
            