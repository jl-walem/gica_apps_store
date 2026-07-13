# GICA Apps Store

Open-source GICA modules for Odoo Community.

This repository hosts the official collection of GICA modules for Odoo, providing accounting, banking, supplier payment management, Peppol, migration and business management tools designed to bridge traditional GICA workflows with the Odoo ecosystem.

---

## Available Modules

### GICA Bank Statement

Manual bank statement entry for Odoo Community.

Main features:

* Manual bank statement entry
* Open Documents Wizard
* Real-time amount calculation
* Customer and supplier reconciliation
* Standard Odoo journal entries
* Belgian accounting workflow
* Full compatibility with standard Odoo accounting and reconciliation mechanisms

The Open Documents Wizard allows accountants to select and combine multiple open customer or supplier documents while the running total is updated in real time. This makes it easy to reconstruct the exact amount appearing on a bank statement using a workflow familiar to many Belgian accounting professionals.

---

### GICA Peppol

Peppol integration for Odoo Community using Cyber-Relais services.

Main features:

* Outbound Peppol document management
* UBL BIS 3.0 generation
* PDF generation
* SFTP transmission
* Inbound purchase invoice reception
* API-based integration
* UBL import into vendor bills
* Individual and batch processing

---

### GICA SEPA Payment

Supplier payment preparation and SEPA Credit Transfer management for Odoo Community.

Main features:

* Supplier payment preparation
* Cash-oriented payment batches
* Payment envelopes
* Partial payments
* Credit notes
* Supplier advances
* Litigation management
* SEPA Credit Transfer (pain.001.001.03)
* One accounting entry per payment batch
* Standard Odoo reconciliation
* Complete workflow tracking

Unlike traditional SEPA export tools, GICA SEPA Payment focuses on supplier payment preparation rather than simply generating SEPA files. It allows accountants to review, prioritise and organise supplier payments according to the company's available cash before generating a standard SEPA Credit Transfer file.

---

## Planned Modules

The repository is intended to host additional GICA modules, including:

* GICA Import
* GICA Migration Tools
* GICA Matching
* GICA Tariff
* Other accounting and business management extensions

---

## Target Versions

| Odoo Version | Status |
|---------------|---------|
| Odoo 17 Community | Supported |
| Odoo 17 Enterprise | Compatible* |
| Odoo 18 Community | Planned |

\* Some modules require the complete Accounting application under Odoo Enterprise.

---

## Languages

Current modules may include:

* English
* Français
* Nederlands

---

## License

Each module contains its own license information.

Unless otherwise specified, modules are distributed under the LGPL-3 license.

---

## Website

https://www.eurologiciel.be

---

## Author

**Jean-Luc Walem**

Eurologiciel SA

Belgium

---

## About GICA

GICA is an ERP solution developed and maintained by Eurologiciel for several decades.

The purpose of this repository is to progressively bring decades of accounting expertise and selected GICA business workflows to the Odoo ecosystem while preserving the flexibility, openness and standard accounting mechanisms of Odoo.
