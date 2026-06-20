# -*- coding: utf-8 -*-

import traceback

from odoo import fields, models, _
from odoo.exceptions import UserError
from lxml import etree
import base64
#import logging
#_logger = logging.getLogger(__name__)

class GicaPeppolPurchase(models.Model):
    _name = "gica.peppol.purchase"
    _description = "GICA Peppol Purchase"
    _inherit = ["mail.thread", "mail.activity.mixin", "gica.peppol.translation.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        default=lambda self: _("New"),
        tracking=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    move_id = fields.Many2one(
        "account.move",
        string="Vendor Bill",
        readonly=True,
        copy=False,
        tracking=True,
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Vendor",
        readonly=True,
        tracking=True,
    )

    document_type = fields.Selection(
        [
            ("invoice", "Invoice"),
            ("credit_note", "Credit Note"),
            ("unknown", "Unknown"),
        ],
        string="Document Type",
        default="unknown",
        required=True,
        tracking=True,
    )

    supplier_reference = fields.Char(
        string="Supplier Reference",
        readonly=True,
    )

    supplier_vat = fields.Char(
        string="Supplier VAT",
        readonly=True,
    )

    supplier_peppol_id = fields.Char(
        string="Supplier Peppol ID",
        readonly=True,
    )

    invoice_date = fields.Date(
        string="Invoice Date",
        readonly=True,
    )

    amount_total = fields.Monetary(
        string="Total",
        currency_field="currency_id",
        readonly=True,
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        readonly=True,
    )

    state = fields.Selection(
        [
            ("received", "Received"),
            ("imported", "Imported"),
            ("error", "Error"),
            ("rejected", "Rejected"),
        ],
        string="Status",
        default="received",
        required=True,
        tracking=True,
    )

    xml_attachment_id = fields.Many2one(
        "ir.attachment",
        string="XML Attachment",
        readonly=True,
        copy=False,
    )

    pdf_attachment_id = fields.Many2one(
        "ir.attachment",
        string="PDF Attachment",
        readonly=True,
        copy=False,
    )

    html_attachment_id = fields.Many2one(
        "ir.attachment",
        string="HTML Attachment",
        readonly=True,
        copy=False,
    )

    error_message = fields.Text(
        string="Error Message",
        readonly=True,
    )

    def _parse_ubl_metadata(self, xml_content):
        root = etree.fromstring(xml_content)

        ns = {
            "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
            "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        }

        tag = etree.QName(root).localname

        if tag == "Invoice":
            document_type = "invoice"
        elif tag == "CreditNote":
            document_type = "credit_note"
        else:
            raise ValueError("Unsupported UBL document type: %s" % tag)

        name = root.findtext("cbc:ID", namespaces=ns)
        invoice_date = root.findtext("cbc:IssueDate", namespaces=ns)

        amount_node = root.find(
            "cac:LegalMonetaryTotal/cbc:PayableAmount",
            namespaces=ns
        )

        amount_total = 0.0
        currency = False

        if amount_node is not None:
            amount_total = float(amount_node.text or 0.0)
            currency = amount_node.get("currencyID")

        supplier_reference = root.findtext(
            "cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName",
            namespaces=ns
        ) or root.findtext(
            "cac:AccountingSupplierParty/cac:Party/cac:PartyName/cbc:Name",
            namespaces=ns
        ) or name

        if not name:
            raise ValueError("Missing UBL document ID")

        if not invoice_date:
            raise ValueError("Missing UBL issue date")

        return {
            "name": name,
            "document_type": document_type,
            "supplier_reference": supplier_reference,
            "invoice_date": invoice_date,
            "amount_total": amount_total,
            "currency": currency,
        }

    def action_open_vendor_bill(self):
        self.ensure_one()
        if not self.move_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Vendor Bill"),
            "res_model": "account.move",
            "res_id": self.move_id.id,
            "view_mode": "form",
            "target": "current",
        }
    def action_import_ubl(self):
        for rec in self:
            if rec.move_id:
                continue

            if not rec.xml_attachment_id:
                rec.write({
                    "state": "error",
                    "error_message": _("No XML attachment found."),
                })
                continue

            try:
                file_data = rec.xml_attachment_id._unwrap_edi_attachments()[0]
                move_type = "in_refund" if rec.document_type == "credit_note" else "in_invoice"

                move = self.env["account.move"].with_company(rec.company_id).create({
                    "move_type": move_type,
                    "company_id": rec.company_id.id,
                })

                decoder = move._get_edi_decoder(file_data, new=True)
                if decoder is None:
                    raise UserError(_("No EDI decoder found for this XML file."))

                imported = decoder(move, file_data, new=True)
                if not imported:
                    raise UserError(_("The XML file could not be imported."))

                rec.write({
                    "move_id": move.id,
                    "partner_id": move.partner_id.id,
                    "supplier_reference": move.ref or rec.supplier_reference,
                    "invoice_date": move.invoice_date,
                    "amount_total": move.amount_total,
                    "currency_id": move.currency_id.id,
                    "state": "imported",
                    "error_message": False,
                })

                rec.xml_attachment_id.write({
                    "res_model": "account.move",
                    "res_id": move.id,
                })

                if rec.pdf_attachment_id:
                    rec.pdf_attachment_id.copy({
                        "res_model": "account.move",
                        "res_id": move.id,
                    })

                if rec.html_attachment_id:
                    rec.html_attachment_id.copy({
                        "res_model": "account.move",
                        "res_id": move.id,
                    })

            except Exception as e:
                rec.write({
                    "state": "error",
                    "error_message": "%s\n\n%s" % (str(e), traceback.format_exc()),
                })

        return True
    
    def unlink(self):
        attachment_ids = []

        for rec in self:
            if rec.state != "received":
                message = "You can only delete Peppol purchase documents in Received status."
                rec._gica_error(message)

            attachment_ids += [
                rec.xml_attachment_id.id,
                rec.pdf_attachment_id.id,
                rec.html_attachment_id.id,
            ]

        attachment_ids = [att_id for att_id in attachment_ids if att_id]

        res = super().unlink()

        attachments = self.env["ir.attachment"].browse(attachment_ids).exists()
        if attachments:
            attachments.unlink()

        return res