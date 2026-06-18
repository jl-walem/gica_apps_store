from odoo import _, models, fields
from lxml import etree
from datetime import datetime

import base64
import io
import re
import paramiko

class GicaPeppolSale(models.Model):
    _name = "gica.peppol.sale"
    _inherit = ["gica.peppol.translation.mixin"]
    _description = "GICA Peppol Sale"

    name = fields.Char(string="Reference", required=True)

    move_id = fields.Many2one(
        "account.move",
        string="Invoice",
        ondelete="cascade",
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
    )

    peppol_status = fields.Selection(
        [
            ("to_generate", "To Generate"),
            ("to_send", "To Send"),
            ("sent", "Sent"),
            ("delivered", "Delivered"),
            ("rejected", "Rejected"),
            ("error", "Error"),
        ],
        default="to_generate",
        string="Status",
    )

    invoice_date = fields.Date(string="Invoice Date")
    partner_vat = fields.Char(string="Customer VAT")
    amount_total = fields.Monetary(string="Total Amount")
    currency_id = fields.Many2one("res.currency", string="Currency")

    sent_date = fields.Datetime(string="Sent Date")
    sftp_filename = fields.Char(string="SFTP Filename")
    delivered_date = fields.Datetime(string="Delivered Date")
    error_message = fields.Text(string="Error Message")
    
    error_stage = fields.Selection(
        [
            ("generate", "Generation"),
            ("send", "Sending"),
        ],
        string="Error Stage",
    )
    
    _sql_constraints = [
        (
            "unique_move_id",
            "unique(move_id)",
            "A Peppol sale record already exists for this invoice.",
        )
    ]

    def action_reset_to_generate(self):
        for rec in self:
            if not (
                rec.peppol_status == "error"
                and rec.error_stage == "generate"
            ):
                message = (
                    "Only Peppol documents with a generation error can be reset to To Generate."
                )
                rec._gica_error(message)

            rec.peppol_status = "to_generate"
            rec.error_message = False
            rec.error_stage = False
            rec.sent_date = False

            if rec.move_id:
                rec.move_id.gica_peppol_status = "to_generate"

        return True

    def action_reset_to_send(self):
        for rec in self:
            if not (
                (rec.peppol_status == "error" and rec.error_stage == "send")
                or rec.peppol_status == "rejected"
            ):
                message = (
                    "Only rejected documents or documents with a sending error can be reset to To Send."
                )
                rec._gica_error(message)

            rec.peppol_status = "to_send"
            rec.error_message = False
            rec.error_stage = False
            rec.sent_date = False

            if rec.move_id:
                rec.move_id.gica_peppol_status = "to_send"

        return True
    
    def action_send_to_cyber_relais(self):
        records = self

        if not records:
            records = self.search([("peppol_status", "=", "to_send")])

        records_to_send = records.filtered(
            lambda r: r.peppol_status == "to_send"
        )

        if not records_to_send:
            message = "No Peppol document to send."
            self._gica_error(message)

        for rec in records_to_send:
            rec.peppol_status = "sent"
            rec.sent_date = fields.Datetime.now()

            if rec.move_id:
                rec.move_id.gica_peppol_status = "sent"

        return True
    
    def action_generate_xml(self):

        for rec in self:

            if rec.peppol_status != "to_generate":
                message = (
                    "Only Peppol documents in To Generate status can be generated."
                )
                rec._gica_error(message)

            xml_mode = rec.move_id.company_id.gica_peppol_xml_mode

            if xml_mode == "existing_xml":

                attachment = self.env["ir.attachment"].search([
                    ("res_model", "=", "account.move"),
                    ("res_id", "=", rec.move_id.id),
                    ("mimetype", "in", ["application/xml", "text/xml"]),
                ], limit=1)

                if not attachment:
                    message = "No XML attachment found."
                    rec.error_message = message
                    rec.peppol_status = "error"
                    rec.error_stage = "generate"

                    if rec.move_id:
                        rec.move_id.gica_peppol_status = "error"

                    continue

                rec.error_message = False
                rec.error_stage = False
                rec.sent_date = False
                rec.peppol_status = "to_send"

                if rec.move_id:
                    rec.move_id.gica_peppol_status = "to_send"

                continue

            generator = self.env["account.edi.xml.ubl_bis3"]

            xml_content, errors = generator._export_invoice(rec.move_id)

            if errors:
                rec.error_message = "\n".join(errors)
                rec.peppol_status = "error"
                rec.error_stage = "generate"

                if rec.move_id:
                    rec.move_id.gica_peppol_status = "error"

                continue

            pdf_attachment = self._get_or_create_invoice_pdf_attachment(rec)

            xml_content = self._embed_pdf_in_ubl_xml(
                xml_content,
                pdf_attachment,
            )

            attachment_name = generator._export_invoice_filename(rec.move_id)

            attachment = self.env["ir.attachment"].create({
                "name": attachment_name,
                "datas": base64.b64encode(xml_content),
                "mimetype": "application/xml",
                "res_model": "account.move",
                "res_id": rec.move_id.id,
            })

            rec.move_id.message_post(
                body="Peppol XML generated.",
                attachment_ids=[attachment.id],
                subtype_xmlid="mail.mt_note",
            )

            rec.error_message = False
            rec.error_stage = False
            rec.sent_date = False
            rec.peppol_status = "to_send"

            if rec.move_id:
                rec.move_id.gica_peppol_status = "to_send"

        return True
    
    def _get_or_create_invoice_pdf_attachment(self, rec):
        report = self.env.ref("account.account_invoices")
        pdf_content, _ = self.env["ir.actions.report"]._render_qweb_pdf(
            report.report_name,
            res_ids=[rec.move_id.id],
        )

        safe_name = rec.move_id.name.replace("/", "_")
        pdf_name = (
            f"{safe_name}_gica_peppol_"
            f"{fields.Datetime.context_timestamp(self, fields.Datetime.now()).strftime('%Y%m%d_%H%M%S')}.pdf"
        )

        pdf_attachment = self.env["ir.attachment"].create({
            "name": pdf_name,
            "datas": base64.b64encode(pdf_content),
            "mimetype": "application/pdf",
            "res_model": "account.move",
            "res_id": rec.move_id.id,
        })

        rec.move_id.message_post(
            body="Invoice PDF generated.",
            attachment_ids=[pdf_attachment.id],
            subtype_xmlid="mail.mt_note",
        )

        return pdf_attachment
    
    def _embed_pdf_in_ubl_xml(self, xml_content, pdf_attachment):

        nsmap = {
            "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
            "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        }

        root = etree.fromstring(xml_content)

        additional_doc = etree.Element(
            "{%s}AdditionalDocumentReference" % nsmap["cac"]
        )

        doc_id = etree.SubElement(
            additional_doc,
            "{%s}ID" % nsmap["cbc"]
        )
        doc_id.text = pdf_attachment.name

        doc_type = etree.SubElement(
            additional_doc,
            "{%s}DocumentType" % nsmap["cbc"]
        )
        doc_type.text = "Commercial invoice PDF"

        attachment_node = etree.SubElement(
            additional_doc,
            "{%s}Attachment" % nsmap["cac"]
        )

        embedded = etree.SubElement(
            attachment_node,
            "{%s}EmbeddedDocumentBinaryObject" % nsmap["cbc"]
        )
        embedded.set("mimeCode", "application/pdf")
        embedded.set("filename", pdf_attachment.name)
        embedded.text = pdf_attachment.datas.decode("utf-8")

        # Insert after existing AdditionalDocumentReference nodes if present,
        # otherwise after AccountingCustomerParty when possible.
        insert_index = None

        children = list(root)

        for index, child in enumerate(children):
            if child.tag == "{%s}AdditionalDocumentReference" % nsmap["cac"]:
                insert_index = index + 1

        if insert_index is None:
            for index, child in enumerate(children):
                if child.tag == "{%s}AccountingCustomerParty" % nsmap["cac"]:
                    insert_index = index + 1
                    break

        if insert_index is None:
            root.append(additional_doc)
        else:
            root.insert(insert_index, additional_doc)

        return etree.tostring(
            root,
            xml_declaration=True,
            encoding="UTF-8",
            pretty_print=True,
        )
    
    def action_send_to_cyber_relais(self):
        for rec in self:
            rec._send_xml_by_sftp()
        return True

    def _send_xml_by_sftp(self):
        self.ensure_one()

        if self.peppol_status != "to_send":
            message = (
                "Only Peppol documents in To Send status can be sent."
            )
            self._gica_error(message)

        attachment = self.env["ir.attachment"].search([
            ("res_model", "=", "account.move"),
            ("res_id", "=", self.move_id.id),
            ("name", "ilike", ".xml"),
        ], limit=1)

        if not attachment:
            message = "No XML attachment found."
            self._set_send_error(message)

        company = self.move_id.company_id

        if not company.peppol_sftp_host:
            message = "Missing Peppol SFTP host."
            self._set_send_error(message)

        if not company.peppol_sftp_user:
            message = "Missing Peppol SFTP user."
            self._set_send_error(message)

        if not company.peppol_sftp_private_key:
            message = "Missing Peppol SFTP private key path."
            self._set_send_error(message)

        xml_content = base64.b64decode(attachment.datas)
        filename = self._prepare_sftp_filename()

        transport = False

        try:
            key_file = io.StringIO(company.peppol_sftp_private_key.strip())
            private_key = paramiko.Ed25519Key.from_private_key_file(
                company.peppol_sftp_private_key
            )

            transport = paramiko.Transport((
                company.peppol_sftp_host,
                company.peppol_sftp_port or 22,
            ))

            transport.connect(
                username=company.peppol_sftp_user,
                pkey=private_key,
            )

            sftp = paramiko.SFTPClient.from_transport(transport)

            with sftp.file("/upload/" + filename, "wb") as remote_file:
                remote_file.write(xml_content)

            sftp.close()

        except Exception as e:
            message = "SFTP send failed: %s" % str(e)
            self._set_send_error(message)

        finally:
            if transport:
                transport.close()

        self.write({
            "peppol_status": "sent",
            "sent_date": fields.Datetime.now(),
            "sftp_filename": filename,
            "error_message": False,
            "error_stage": False,
        })

        if self.move_id:
            self.move_id.gica_peppol_status = "sent"

    def _set_send_error(self, message):
        self.write({
            "peppol_status": "error",
            "error_message": message,
            "error_stage": "send",
        })

        if self.move_id:
            self.move_id.gica_peppol_status = "error"

        self._gica_error(message)

    def _prepare_sftp_filename(self):
        self.ensure_one()

        invoice_name = self.move_id.name or self.name or "invoice"
        invoice_name = re.sub(r"[^A-Za-z0-9_.-]", "_", invoice_name)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        return "%s_%s.xml" % (invoice_name, timestamp)
