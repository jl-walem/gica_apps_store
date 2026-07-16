# -*- coding: utf-8 -*-

{
    "name": "GICA SEPA Payment",
    "summary": "Prepare, prioritise and group supplier payments before SEPA export",
    "version": "17.0.1.0.1",
    "category": "Accounting",
    "author": "Eurologiciel",
    "website": "https://www.eurologiciel.be/odoo",
    "license": "LGPL-3",
    "depends": [
        "account",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/ir_rule.xml",
        "views/sepa_move_info_views.xml",
        "views/sepa_envelope_views.xml",
        "views/sepa_prepare_wizard_views.xml",
        "views/sepa_candidate_views.xml",
        "views/res_company_views.xml",
        "views/account_move_views.xml",
        "views/sepa_add_all_ready_wizard_views.xml",
        "views/sepa_select_ready_wizard_views.xml",
        "views/sepa_add_manual_payment_wizard_views.xml",
        "views/sepa_bank_profile_views.xml",
        "views/sepa_menu_views.xml",
        "views/gica_sepa_i18n_terms.xml",
    ],
    "images": [
        "static/description/cover.png",
    ],
    "assets": {
        "web.assets_backend": [
            "gica_sepa_payment/static/src/css/sepa_candidate.css",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}