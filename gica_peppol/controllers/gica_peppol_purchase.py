# -*- coding: utf-8 -*-

import base64
import json

from odoo import http, fields
from odoo.http import request

from html import unescape


class GicaPeppolPurchaseController(http.Controller):

    @http.route(
        "/gica_peppol/inbound/purchase",
        type="json",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def inbound_purchase(self, **payload):
        company_code = payload.get("company_code")

        if not company_code:
            return {"status": "error", "message": "Missing company_code"}

        company = request.env["res.company"].sudo().search([
            ("peppol_sftp_user", "=", company_code),
        ], limit=1)

        if not company:
            return {"status": "error", "message": "Invalid company_code"}

        xml_content = base64.b64decode(payload.get("xml_base64") or "")

        metadata = request.env["gica.peppol.purchase"].sudo()._parse_ubl_metadata(xml_content)
        
        currency = request.env["res.currency"].sudo().search(
            [("name", "=", metadata["currency"])],
            limit=1
        )

        if not currency:
            raise ValueError(
                f"Currency '{metadata['currency']}' not found in Odoo"
            )
        
        purchase = request.env["gica.peppol.purchase"].sudo().create({
            "company_id": company.id,
            "name": unescape(metadata["name"]),
            "document_type": metadata["document_type"],
            "supplier_reference": unescape(metadata["supplier_reference"]),
            "invoice_date": metadata["invoice_date"],
            "amount_total": metadata["amount_total"],
            "currency_id": currency.id,
        })

        def create_attachment(field_name, filename_key, content_key, default_name, mimetype):
            content = payload.get(content_key)
            if not content:
                return False

            attachment = request.env["ir.attachment"].sudo().create({
                "name": payload.get(filename_key) or default_name,
                "type": "binary",
                "datas": content,
                "res_model": "gica.peppol.purchase",
                "res_id": purchase.id,
                "mimetype": mimetype,
            })
            purchase.write({field_name: attachment.id})
            return attachment.id

        create_attachment(
            "xml_attachment_id",
            "xml_filename",
            "xml_base64",
            "invoice.xml",
            "application/xml",
        )

        create_attachment(
            "pdf_attachment_id",
            "pdf_filename",
            "pdf_base64",
            "invoice.pdf",
            "application/pdf",
        )

        create_attachment(
            "html_attachment_id",
            "html_filename",
            "html_base64",
            "invoice.html",
            "text/html",
        )

        return {
            "status": "ok",
            "purchase_id": purchase.id,
            "purchase_name": purchase.name,
            "state": purchase.state,
            "message": "Peppol purchase received",
        }