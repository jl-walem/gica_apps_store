# GICA Peppol

GICA Peppol is an Odoo 17 Community module developed by Jean-Luc Walem to connect Odoo with external Peppol services operated by Cyber-Relais.

The module provides both outbound and inbound Peppol integration while keeping Odoo focused on accounting and document management.

## Features

### Outbound Peppol Sales

- Create Peppol sales records from posted customer invoices
- Generate UBL BIS 3.0 XML from Odoo invoices
- Generate or reuse PDF attachments
- Send XML/PDF files to Cyber-Relais through SFTP
- Track outbound document status
- Multi-company configuration

### Inbound Peppol Purchases

- Receive vendor invoices through an API endpoint
- Store original UBL XML, PDF and HTML attachments
- Create an intermediate Peppol purchase record
- Import UBL documents into Odoo vendor bills
- Support individual and batch UBL import
- Keep vendor bills in draft for user review

## Important note about inbound documents

The inbound API expects a pure UBL Invoice or Credit Note document.

If the Peppol platform receives a Standard Business Document (SBD), the SBD envelope must be extracted by the external Peppol platform before sending the UBL file to Odoo.

## Configuration

Go to:

**Settings > Companies > Peppol**

Configure:

- XML Mode
- SFTP Host
- SFTP Port
- SFTP User
- Private Key Path

The SFTP User is also used as the company code for inbound API routing.

## Menus

The module adds:

**GICA > Peppol > Peppol Sales**

**GICA > Peppol > Peppol Purchases**

## Dependencies

- account
- mail

## License

LGPL-3

## Author

Jean-Luc Walem  
Eurologiciel  
https://www.eurologiciel.be
