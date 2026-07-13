from lxml import etree

from odoo import fields, _

SEPA_NS = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"


class GicaSepaXmlGenerator:
    
    def __init__(self, env, envelope):
        self.env = env
        self.envelope = envelope

    def generate(self):
        self._check_envelope()

        document = etree.Element(
            "Document",
            nsmap={None: SEPA_NS},
        )

        root = etree.SubElement(document, "CstmrCdtTrfInitn")
        self._generate_group_header(root)
        self._generate_payment_information(root)
       
        return etree.tostring(
            document,
            xml_declaration=True,
            encoding="UTF-8",
            pretty_print=True,
        )

    def _check_envelope(self):
        if not self.envelope.line_ids:
            message = "You cannot generate XML for an empty envelope."
            self.env["gica.sepa.move.info"]._gica_error(message)


        if self.envelope.currency_id.name != "EUR":
            message = "SEPA XML can only be generated in EUR."
            self.env["gica.sepa.move.info"]._gica_error(message)


        if not self.envelope.execution_date:
            message = "Execution date is required to generate the SEPA XML."
            self.env["gica.sepa.move.info"]._gica_error(message)

    def _generate_group_header(self, parent):
        envelope = self.envelope

        group_header = etree.SubElement(parent, "GrpHdr")

        etree.SubElement(group_header, "MsgId").text = envelope.name
        etree.SubElement(group_header, "CreDtTm").text = (
            fields.Datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        )
        etree.SubElement(group_header, "BtchBookg").text = "true"
        etree.SubElement(group_header, "NbOfTxs").text = str(len(envelope.line_ids))
        etree.SubElement(
            group_header,
            "CtrlSum",
        ).text = self._format_amount(envelope.total_amount)

        initiating_party = etree.SubElement(group_header, "InitgPty")
        etree.SubElement(
            initiating_party,
            "Nm",
        ).text = envelope.company_id.name

        company_vat = (envelope.company_id.vat or "").upper().replace(" ", "")

        if (
            company_vat
            and not company_vat[:2].isalpha()
            and envelope.company_id.country_id.code == "BE"
        ):
            company_vat = f"BE{company_vat}"

        if company_vat:
            party_id = etree.SubElement(initiating_party, "Id")
            org_id = etree.SubElement(party_id, "OrgId")
            other = etree.SubElement(org_id, "Othr")

            etree.SubElement(other, "Id").text = company_vat

            scheme = etree.SubElement(other, "SchmeNm")
            etree.SubElement(scheme, "Cd").text = "TXID"
    
    def _generate_payment_information(self, parent):
        envelope = self.envelope
        bank_account = envelope.sepa_profile_id.bank_journal_id.bank_account_id

        if not bank_account:
            message = "The SEPA journal has no bank account."
            self.env["gica.sepa.move.info"]._gica_error(message)

        if not bank_account.acc_number:
            message = "The company bank account has no IBAN."
            self.env["gica.sepa.move.info"]._gica_error(message)
            
        pmt_inf = etree.SubElement(parent, "PmtInf")

        etree.SubElement(pmt_inf, "PmtInfId").text = envelope.name
        etree.SubElement(pmt_inf, "PmtMtd").text = "TRF"

        pmt_tp_inf = etree.SubElement(pmt_inf, "PmtTpInf")
        svc_lvl = etree.SubElement(pmt_tp_inf, "SvcLvl")
        etree.SubElement(svc_lvl, "Cd").text = "SEPA"

        etree.SubElement(pmt_inf, "ReqdExctnDt").text = envelope.execution_date.strftime(
            "%Y-%m-%d"
        )

        dbtr = etree.SubElement(pmt_inf, "Dbtr")
        etree.SubElement(dbtr, "Nm").text = envelope.company_id.name

        dbtr_acct = etree.SubElement(pmt_inf, "DbtrAcct")
        dbtr_acct_id = etree.SubElement(dbtr_acct, "Id")
        etree.SubElement(dbtr_acct_id, "IBAN").text = self._clean_iban(
            bank_account.acc_number
        )

        dbtr_agt = etree.SubElement(pmt_inf, "DbtrAgt")
        fin_instn_id = etree.SubElement(dbtr_agt, "FinInstnId")

        if bank_account.bank_id and bank_account.bank_id.bic:
            etree.SubElement(
                fin_instn_id,
                "BIC",
            ).text = bank_account.bank_id.bic
        else:
            other = etree.SubElement(fin_instn_id, "Othr")
            etree.SubElement(other, "Id").text = "NOTPROVIDED"

        for line in envelope.line_ids:
            self._generate_transaction(pmt_inf, line)

 
    def _generate_transaction(self, parent, line):
        creditor_bank = self._get_creditor_bank(line)
        partner = line.move_line_id.partner_id.commercial_partner_id

        tx = etree.SubElement(parent, "CdtTrfTxInf")

        pmt_id = etree.SubElement(tx, "PmtId")
        etree.SubElement(pmt_id, "EndToEndId").text = f"{self.envelope.name}-{line.id}"

        amt = etree.SubElement(tx, "Amt")
        etree.SubElement(
            amt,
            "InstdAmt",
            Ccy="EUR",
        ).text = self._format_amount(line.payment_amount)

        if creditor_bank.bank_id and creditor_bank.bank_id.bic:
            cdtr_agt = etree.SubElement(tx, "CdtrAgt")
            fin_instn_id = etree.SubElement(cdtr_agt, "FinInstnId")
            etree.SubElement(
                fin_instn_id,
                "BIC",
            ).text = creditor_bank.bank_id.bic

        cdtr = etree.SubElement(tx, "Cdtr")
        etree.SubElement(cdtr, "Nm").text = partner.name

        cdtr_acct = etree.SubElement(tx, "CdtrAcct")
        cdtr_acct_id = etree.SubElement(cdtr_acct, "Id")
        etree.SubElement(cdtr_acct_id, "IBAN").text = self._clean_iban(
            creditor_bank.acc_number
        )

        etree.SubElement(tx, "ChrgBr").text = "SLEV"

        self._generate_remittance_information(tx, line)


    def _generate_remittance_information(self, parent, line):
        communication = (
            line.communication
            or line.communication_auto
            or self.envelope.name
        )

        communication = (communication or "").strip()[:140]

        rmt_inf = etree.SubElement(parent, "RmtInf")
        etree.SubElement(rmt_inf, "Ustrd").text = communication

    def _get_creditor_bank(self, line):
        partner = line.move_line_id.partner_id.commercial_partner_id

        if not partner:
            message = "Payment line %s has no supplier."
            self.env["gica.sepa.move.info"]._gica_error(message,line.display_name)

        bank = self.env["res.partner.bank"].search([
            ("partner_id", "=", partner.id),
        ], limit=1)

        if not bank:
            message = "Supplier %s has no bank account."
            self.env["gica.sepa.move.info"]._gica_error(message,partner.display_name)

        if not bank.acc_number:
            message = "Supplier %s has no IBAN."
            self.env["gica.sepa.move.info"]._gica_error(message,partner.display_name)

        return bank

    def _clean_iban(self, iban):
        return (iban or "").replace(" ", "").upper()

    def _format_amount(self, amount):
        return f"{amount:.2f}"