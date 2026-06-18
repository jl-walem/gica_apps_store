from odoo import models, fields


class ResCompany(models.Model):
    _inherit = "res.company"

    gica_peppol_xml_mode = fields.Selection(
        [
            ("odoo_bis3", "Generate Odoo BIS3 XML"),
            ("existing_xml", "Use existing XML attachment"),
        ],
        string="XML Mode",
        default="odoo_bis3",
    )

    peppol_sftp_host = fields.Char(
        string="SFTP Host",
        default="ap.eurologiciel.be",
    )

    peppol_sftp_port = fields.Integer(
        string="SFTP Port",
        default=22,
    )

    peppol_sftp_user = fields.Char(
        string="SFTP User",
    )

    peppol_sftp_private_key = fields.Text(
        string="Private Key path",
    )
    
