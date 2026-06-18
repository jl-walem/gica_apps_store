# -*- coding: utf-8 -*-

import base64
import json

from odoo import http, fields
from odoo.http import request


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

        name = payload.get("name") or payload.get("supplier_reference") or "Inbound Peppol"

        purchase = request.env["gica.peppol.purchase"].sudo().create({
            "name": name,
            "company_id": company.id,
            "document_type": payload.get("document_type") or "unknown",
            "supplier_reference": payload.get("supplier_reference"),
            "supplier_vat": payload.get("supplier_vat"),
            "supplier_peppol_id": payload.get("supplier_peppol_id"),
            "invoice_date": payload.get("invoice_date"),
            "amount_total": payload.get("amount_total") or 0.0,
            "currency_id": request.env["res.currency"].sudo().search([
                ("name", "=", payload.get("currency") or company.currency_id.name)
            ], limit=1).id or company.currency_id.id,
            "state": "received",
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