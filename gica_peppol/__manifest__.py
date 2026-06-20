{
"name": "GICA Peppol",
"version": "17.0.2.0.0",
"summary": "Peppol integration for Odoo using Cyber-Relais services",

```
"description": """
```

# GICA Peppol

Peppol integration for Odoo Community.

Main features:

* Outbound Peppol sales documents
* UBL BIS 3.0 XML generation
* SFTP transmission through Cyber-Relais services
* Inbound Peppol purchase documents
* Vendor bill creation from UBL documents
* Multi-company support
  """,

  "author": "Jean-Luc Walem",
  "website": "https://www.eurologiciel.be/odoo/",
  "category": "Accounting",
  "license": "LGPL-3",

  "images": [
  "static/description/cover.png",
  ],

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

