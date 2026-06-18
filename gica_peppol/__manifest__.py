{
    "name": "GICA Peppol",
    "version": "17.0.2.0.0",
    "author": "Jean-Luc Walem",
    "website": "https://www.eurologiciel.be",
    "category": "Accounting",
    "summary": "Peppol integration for Odoo using Cyber-Relais services",
    "license": "LGPL-3",
    "depends": [
        "account",
        "mail",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/gica_peppol_sale_views.xml",
	"views/gica_peppol_purchase_views.xml",
        "views/gica_peppol_menu.xml",
        "views/gica_peppol_i18n_terms.xml",
        "views/res_company_views.xml",
	"data/server_actions.xml",
    ],
    "installable": True,
    "application": True,
}
