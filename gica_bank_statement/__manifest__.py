{
    'name': 'GICA Bank Statement',
    'version': '17.0.1.0.0',
    'summary': 'Simple Belgian-style bank statement entry',
    'description': """
GICA Bank Statement
===================

Simple manual bank statement entry for Odoo Community.

Main features:
- Simple Belgian-style statement entry
- Manual allocation of customer/supplier documents
- Compatible with Odoo reconciliation
- Designed for Belgian accountants and SMEs
""",
    'author': 'Eurologiciel',
    'website': 'https://www.eurologiciel.be/odoo',
    'category': 'Accounting',
    'license': 'LGPL-3',

    'images': [
    	'static/description/cover.png',
    ],

    'depends': [
        'account',
    ],

    'data': [
         'security/ir.model.access.csv',
         'views/bank_statement_views.xml',
         'views/open_items_wizard_views.xml',
         'views/menu.xml',
    ],

    'installable': True,
    'application': False,
}
