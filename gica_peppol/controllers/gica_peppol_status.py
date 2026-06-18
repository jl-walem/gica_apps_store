from odoo import http, fields
from odoo.http import request


class GicaPeppolStatusController(http.Controller):

    @http.route(
        "/gica_peppol/status",
        type="json",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def update_status(self, **payload):

        sftp_user = payload.get("sftp_user")
        sftp_filename = payload.get("sftp_filename")
        status = payload.get("status")
        message = payload.get("message") or False
        delivered_at = payload.get("delivered_at")

        if not sftp_user:
            return {
                "success": False,
                "error": "Missing sftp_user",
            }

        if not sftp_filename:
            return {
                "success": False,
                "error": "Missing sftp_filename",
            }

        if status not in (
            "delivered",
            "rejected",
            "error",
        ):
            return {
                "success": False,
                "error": "Invalid status",
            }

        company = request.env["res.company"].sudo().search([
            ("peppol_sftp_user", "=", sftp_user),
        ], limit=1)

        if not company:
            return {
                "success": False,
                "error": "Unknown SFTP user",
            }

        rec = request.env["gica.peppol.sale"].sudo().search([
            ("sftp_filename", "=", sftp_filename),
            ("move_id.company_id", "=", company.id),
        ], limit=1)

        if not rec:
            return {
                "success": False,
                "error": "Document not found",
            }

        values = {}

        if status == "delivered":

            values = {
                "peppol_status": "delivered",
                "error_message": False,
                "error_stage": False,
            }

            if delivered_at:
                values["delivered_date"] = (
                    fields.Datetime.to_datetime(
                        delivered_at
                    )
                )
            else:
                values["delivered_date"] = (
                    fields.Datetime.now()
                )

        elif status == "rejected":

            values = {
                "peppol_status": "rejected",
                "error_message": message,
            }

        elif status == "error":

            values = {
                "peppol_status": "error",
                "error_stage": "send",
                "error_message": message,
            }

        rec.write(values)

        if rec.move_id:
            rec.move_id.sudo().write({
                "gica_peppol_status":
                    values["peppol_status"]
            })

        return {
            "success": True,
        }
