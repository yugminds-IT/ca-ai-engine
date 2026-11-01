"""
CSI / FVU return file generator.

Produces the pipe-delimited .txt return file that NSDL's File Validation
Utility (FVU) accepts for e-filing TDS returns (Form 24Q and 26Q).

Record layout follows NSDL FVU specification v8.x:
  BH — Batch Header     (1 per file)
  CD — Challan Detail   (1 per challan)
  DD — Deductee Detail  (1 per deductee under each challan)
  BT — Batch Trailer    (1 per file)
"""

from decimal import Decimal
from typing import Optional

from features.tds.schemas.challan import ChallanData
from features.tds.schemas.deductee import DeducteeRecord
from features.tds.schemas.return_file import (
    ChallanWithDeductees,
    TDSReturn,
    TDSReturn24Q,
    TDSReturn26Q,
)

SEP = "|"
CRLF = "\r\n"  # NSDL FVU requires Windows line endings


def _f(*values) -> str:
    """Join fields with pipe separator."""
    return SEP.join(str(v) if v is not None else "" for v in values)


def _amt(value: Decimal) -> str:
    """Format decimal amount as integer string (NSDL stores paise-less amounts)."""
    return str(int(value))


class CSIGenerator:
    """Generate NSDL FVU-compatible TDS return files."""

    # ------------------------------------------------------------------ public

    def generate_24q(self, return_data: TDSReturn24Q) -> str:
        return self._generate(return_data)

    def generate_26q(self, return_data: TDSReturn26Q) -> str:
        return self._generate(return_data)

    # ----------------------------------------------------------------- private

    def _generate(self, r: TDSReturn) -> str:
        lines: list[str] = []

        lines.append(self._batch_header(r))

        for bundle in r.challans:
            lines.append(self._challan_detail(bundle))
            for deductee in bundle.deductees:
                lines.append(self._deductee_detail(deductee, r.form_type))

        lines.append(self._batch_trailer(len(lines) + 1))  # +1 for BT itself

        return CRLF.join(lines) + CRLF

    # ---------------------------------------------------------------- BH record

    def _batch_header(self, r: TDSReturn) -> str:
        d = r.deductor
        last_challan = r.challans[-1].challan if r.challans else None

        return _f(
            "BH",                               # 1  Record type
            r.form_type,                        # 2  Form number
            r.financial_year,                   # 3  Financial year
            r.quarter,                          # 4  Quarter
            d.tan,                              # 5  TAN of deductor
            d.pan or "",                        # 6  PAN of deductor
            r.assessment_year,                  # 7  Assessment year
            d.name,                             # 8  Name of deductor
            d.branch or "",                     # 9  Branch / division
            d.address_line1,                    # 10 Address line 1
            d.address_line2,                    # 11 Address line 2
            d.address_line3,                    # 12 Address line 3
            d.address_line4,                    # 13 Address line 4
            d.address_line5,                    # 14 Address line 5
            d.pincode,                          # 15 Pincode
            d.std_code,                         # 16 STD code
            d.phone,                            # 17 Phone
            "",                                 # 18 Alt STD code
            "",                                 # 19 Alt phone
            d.email,                            # 20 Email
            d.responsible_name,                 # 21 Person responsible name
            d.responsible_designation,          # 22 Designation
            d.responsible_pan,                  # 23 Person responsible PAN
            "C" if r.is_correction else "O",    # 24 Original / Correction
            r.previous_rrr_no or "",            # 25 Previous RRR no.
            str(r.total_challans),              # 26 Total challans
            _amt(r.total_tax_deposited),        # 27 Total tax deposited
            last_challan.challan_no if last_challan else "",   # 28 Last challan TV no.
            last_challan.challan_deposit_ddmmyyyy() if last_challan else "",  # 29 Last tender date
            "",                                 # 30 Remarks
        )

    # ---------------------------------------------------------------- CD record

    def _challan_detail(self, bundle: ChallanWithDeductees) -> str:
        c = bundle.challan
        # For 24Q salary, section code field is left blank in CD record
        section_in_cd = "" if c.nature_of_payment in ("92A", "92B") else c.nature_of_payment

        return _f(
            "CD",                               # 1  Record type
            c.bsr_code,                         # 2  BSR code
            c.challan_deposit_ddmmyyyy(),        # 3  Date of deposit (DDMMYYYY)
            c.challan_no,                       # 4  Challan serial number
            section_in_cd,                      # 5  Section code (blank for salary)
            _amt(c.tax),                        # 6  TDS amount
            _amt(c.interest),                   # 7  Interest
            _amt(c.penalty + c.fee_234e),       # 8  Others
            _amt(c.total_amount),               # 9  Total amount
            str(bundle.deductee_count),         # 10 Number of deductees
            "N",                                # 11 Challan correction indicator
            c.challan_no,                       # 12 Last transfer voucher no.
            c.challan_deposit_ddmmyyyy(),        # 13 Last challan tender date
            "N",                                # 14 Book entry indicator (N=bank/cash)
        )

    # ---------------------------------------------------------------- DD record

    def _deductee_detail(self, d: DeducteeRecord, form_type: str) -> str:
        pay_date = d.date_ddmmyyyy(d.payment_date)
        credit_date = d.date_ddmmyyyy(d.credit_date)
        cert_date = d.date_ddmmyyyy(d.certificate_date)
        total_tax = d.total_tax if d.total_tax else d.tds_deducted

        return _f(
            "DD",                                       # 1  Record type
            str(d.serial_no),                           # 2  Serial number
            d.pan,                                      # 3  PAN
            d.name,                                     # 4  Name
            _amt(d.amount_paid),                        # 5  Amount paid/credited
            _amt(d.tds_deducted),                       # 6  TDS deducted
            _amt(d.surcharge),                          # 7  Surcharge
            _amt(d.education_cess),                     # 8  Education cess
            _amt(total_tax),                            # 9  Total tax deducted
            pay_date,                                   # 10 Date of payment (DDMMYYYY)
            credit_date,                                # 11 Date of credit (DDMMYYYY)
            d.deductee_type.value,                      # 12 O=Ordinary, S=Senior citizen
            d.lower_deduction_reason.value,             # 13 Lower/nil deduction reason
            d.certificate_no or "",                     # 14 Certificate number
            d.section,                                  # 15 Section code (92A/92B/194J…)
            d.last_pan_used or d.pan,                   # 16 Last PAN used
            _amt(d.amount_paid),                        # 17 Gross amount paid
            cert_date,                                  # 18 Date of certificate
        )

    # ---------------------------------------------------------------- BT record

    def _batch_trailer(self, total_records: int) -> str:
        return _f("BT", str(total_records))
