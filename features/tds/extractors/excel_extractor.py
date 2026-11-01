"""
Extract TDS deductee records from salary breakup / deductee Excel sheets.

Handles variable column naming conventions across different client formats.
Salary (24Q), Professional (26Q-194J), and Rent (26Q-194I) share the same
extractor; the tds_type param determines which column aliases to prioritise.
"""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

import pandas as pd
from loguru import logger

from features.tds.schemas.deductee import DeducteeRecord, DeducteeType, LowerDeductionReason


# ---------------------------------------------------------------------------
# Column alias maps — each value is a list of accepted header names (lowercase)
# ---------------------------------------------------------------------------
_COMMON_ALIASES: dict[str, list[str]] = {
    "serial_no": ["sr no", "sr. no", "s.no", "sl no", "sno", "serial no", "serial number"],
    "name": ["employee name", "name", "deductee name", "vendor name", "party name"],
    "pan": ["pan", "pan no", "pan number", "permanent account number"],
    "amount_paid": [
        "gross salary", "gross amount", "amount paid", "salary", "total salary",
        "amount paid / credited", "amount credited", "professional fees", "rent paid",
        "annual gross", "annual gross salary", "ctc", "annual ctc",
    ],
    "tds_deducted": [
        "tds", "tds deducted", "tax deducted", "tds amount", "tax deducted at source",
        "tds this quarter", "tds q4", "tds q3", "tds q2", "tds q1",
    ],
    "surcharge": ["surcharge"],
    "education_cess": ["cess", "education cess", "health and education cess"],
    "section": ["section", "section code", "nature of payment"],
    "payment_date": [
        "payment date", "date of payment", "date paid", "paid date",
        "salary payment date", "disbursement date",
    ],
    "credit_date": [
        "credit date", "date of credit", "credited date", "date credited",
    ],
    "deductee_type": [
        "deductee type", "employee type", "type", "resident type",
        "senior citizen", "category",
    ],
    "lower_deduction_reason": [
        "lower deduction reason", "lower deduction", "nil deduction reason",
        "reason for lower deduction", "exemption reason", "deduction reason",
        "lower / nil deduction reason",
    ],
    "certificate_no": [
        "certificate no", "certificate number", "cert no", "cert number",
        "lower deduction certificate no", "12c certificate no", "certificate serial no",
    ],
    "certificate_date": [
        "certificate date", "cert date", "date of certificate",
        "certificate expiry date", "validity date",
    ],
    "employee_ref_no": [
        "employee ref no", "employee reference no", "employee id", "emp id",
        "employee code", "emp code", "staff id", "staff code",
        "employee number", "emp no",
    ],

    # --- Form 24Q salary breakup fields ---
    "salary_u_s_17_1": [
        "salary u/s 17(1)", "salary 17(1)", "basic salary + da", "basic + da",
        "salary as per 17(1)", "gross salary 17(1)",
    ],
    "perquisites_u_s_17_2": [
        "perquisites u/s 17(2)", "perquisites 17(2)", "perquisites", "perk value",
        "value of perquisites",
    ],
    "profit_in_lieu_u_s_17_3": [
        "profit in lieu u/s 17(3)", "profit in lieu 17(3)", "profit in lieu of salary",
    ],
    "total_gross_salary": [
        "total gross salary", "total salary", "gross total salary",
    ],
    "entertainment_allowance_deduction": [
        "entertainment allowance deduction", "entertainment allowance", "entertain allowance",
    ],
    "professional_tax": [
        "professional tax", "prof tax", "pt", "p.tax",
    ],
    "hra_exemption": [
        "hra exemption", "hra", "house rent allowance exemption", "hra exempt",
        "exemption u/s 10(13a)", "10(13a)",
    ],
    "lta_exemption": [
        "lta exemption", "lta", "leave travel allowance exemption", "lta exempt",
        "exemption u/s 10(5)", "10(5)",
    ],
    "standard_deduction_16ia": [
        "standard deduction", "standard deduction u/s 16(ia)", "std deduction",
        "deduction u/s 16(ia)", "16(ia)",
    ],
    "other_income_reported": [
        "other income", "other income reported", "income from house property",
        "house property income", "other sources income",
    ],
    "deduction_80c": [
        "80c", "section 80c", "deduction 80c", "80c deductions",
        "lic + pf + ppf + elss", "lic/pf/ppf",
    ],
    "deduction_80ccd_1b": [
        "80ccd(1b)", "nps additional", "nps 50000", "additional nps",
        "deduction 80ccd(1b)",
    ],
    "deduction_80ccd_2": [
        "80ccd(2)", "nps employer", "employer nps contribution",
        "deduction 80ccd(2)",
    ],
    "deduction_80d": [
        "80d", "health insurance", "medical insurance premium", "deduction 80d",
        "section 80d",
    ],
    "deduction_80e": [
        "80e", "education loan interest", "deduction 80e", "section 80e",
    ],
    "deduction_80g": [
        "80g", "donation", "donations 80g", "deduction 80g", "section 80g",
    ],
    "deduction_80tta": [
        "80tta", "savings bank interest", "deduction 80tta",
    ],
    "deduction_80ttb": [
        "80ttb", "interest on deposits senior", "deduction 80ttb",
    ],
    "deduction_80u": [
        "80u", "disability deduction", "deduction 80u", "section 80u",
    ],
    "total_deductions_vi_a": [
        "total vi-a deductions", "total chapter via", "total deductions vi-a",
        "chapter vi-a", "total deductions chapter via",
    ],
    "rebate_87a": [
        "rebate 87a", "rebate u/s 87a", "section 87a rebate", "tax rebate",
    ],
    "relief_89": [
        "relief 89", "relief u/s 89", "section 89 relief", "arrear relief",
    ],
    "tds_by_previous_employer": [
        "tds by previous employer", "tds previous employer", "prev employer tds",
        "tds deducted by previous employer",
    ],
    "tds_q1": ["tds q1", "q1 tds", "tds april-june", "quarter 1 tds"],
    "tds_q2": ["tds q2", "q2 tds", "tds july-sept", "quarter 2 tds"],
    "tds_q3": ["tds q3", "q3 tds", "tds oct-dec", "quarter 3 tds"],
    "tds_q4": ["tds q4", "q4 tds", "tds jan-march", "quarter 4 tds"],
    "tds_total": ["total tds", "annual tds", "tds total", "total tax deducted annual"],
    "tax_regime": [
        "tax regime", "regime", "old/new regime", "new regime", "old regime",
        "regime opted",
    ],

    # --- Form 27Q (non-resident) fields ---
    "country_of_residence": [
        "country of residence", "country", "resident country", "nationality",
    ],
    "tax_residency_certificate_no": [
        "trc no", "trc number", "tax residency certificate", "trc",
        "tax residency certificate no",
    ],
    "nature_of_remittance": [
        "nature of remittance", "remittance type", "nature of payment (nr)",
        "type of remittance",
    ],
    "remittance_currency": [
        "currency", "remittance currency", "foreign currency",
    ],
    "remittance_amount_foreign_currency": [
        "foreign currency amount", "amount in foreign currency",
        "remittance amount (foreign currency)", "amount (fc)",
    ],
    "dtaa_article": [
        "dtaa article", "dtaa clause", "treaty article", "dtaa provision",
    ],
    "dtaa_rate": [
        "dtaa rate", "treaty rate", "dtaa tds rate", "rate under dtaa",
    ],
    "form_15ca_ack_no": [
        "form 15ca ack no", "15ca ack", "15ca acknowledgement", "form 15ca no",
    ],
    "form_15cb_cert_no": [
        "form 15cb cert no", "15cb certificate", "ca certificate no", "15cb no",
    ],

    # --- Form 27EQ (TCS) fields ---
    "buyer_pan": [
        "buyer pan", "buyer pan no", "purchaser pan", "licensee pan", "lessee pan",
    ],
    "buyer_name": [
        "buyer name", "purchaser name", "licensee name", "lessee name",
    ],
    "section_206c": [
        "section 206c", "206c", "tcs section", "nature of goods (206c)",
    ],
    "nature_of_goods_or_services": [
        "nature of goods", "goods/services", "nature of goods or services",
        "goods description", "nature of collection",
    ],
    "amount_collected": [
        "amount collected", "sale amount", "collection amount",
        "amount on which tcs collected",
    ],
    "tcs_collected": [
        "tcs collected", "tcs amount", "tax collected", "tcs deducted",
    ],
    "tcs_rate": [
        "tcs rate", "rate of tcs", "tax collection rate",
    ],
    "date_of_collection": [
        "date of collection", "collection date", "date of receipt",
        "date of tcs collection",
    ],

    # --- Form 26QB (property) fields ---
    "buyer_pan_1": ["buyer pan 1", "buyer 1 pan", "purchaser pan 1"],
    "buyer_name_1": ["buyer name 1", "buyer 1 name", "purchaser name 1"],
    "seller_pan_1": ["seller pan 1", "seller 1 pan", "vendor pan 1"],
    "seller_name_1": ["seller name 1", "seller 1 name", "vendor name 1"],
    "total_value_of_property": [
        "total property value", "property value", "sale consideration",
        "total consideration", "total value of property",
    ],
    "amount_paid_this_installment": [
        "amount paid this installment", "installment amount", "amount paid now",
        "payment amount",
    ],
    "date_of_agreement": [
        "date of agreement", "agreement date", "sale deed date",
    ],
    "property_address": [
        "property address", "property location", "flat address", "plot address",
    ],

    # --- Form 26QC (rent) fields ---
    "tenant_pan": ["tenant pan", "tenant pan no", "lessee pan"],
    "landlord_pan": ["landlord pan", "owner pan", "lessor pan", "landlord pan no"],
    "monthly_rent": [
        "monthly rent", "rent per month", "monthly rental", "rent amount",
    ],
    "total_rent_paid": [
        "total rent paid", "annual rent", "total rent", "yearly rent",
    ],
    "from_date": [
        "from date", "rent from", "period from", "rental from date",
    ],
    "to_date": [
        "to date", "rent to", "period to", "rental to date",
    ],

    # --- Form 26QD / 26QE (e-commerce / VDA) fields ---
    "participant_pan": [
        "participant pan", "seller pan", "e-commerce participant pan",
        "vendor pan",
    ],
    "gross_amount": [
        "gross amount", "total amount", "sale amount (ecommerce)",
        "gross sales amount",
    ],
    "nature_of_vda": [
        "nature of vda", "vda type", "crypto type", "nft type",
        "virtual digital asset type",
    ],
    "consideration_amount": [
        "consideration amount", "sale consideration (vda)", "vda amount",
        "crypto sale amount",
    ],
}

def _col_to_snake(name: str) -> str:
    """'House Rent Allowance ' → 'house_rent_allowance'"""
    return re.sub(r"[^a-zA-Z0-9]+", "_", str(name).strip()).strip("_").lower()


_TDS_TYPE_SECTION_DEFAULT = {
    "salary": "92B",
    "professional": "194J",
    "rent": "194I",
}


class ExcelExtractor:
    """Parse Excel salary/deductee sheets into DeducteeRecord lists."""

    def extract(
        self, file_path: str | Path, tds_type: str = "salary"
    ) -> list[DeducteeRecord]:
        df = self._load(file_path)
        df = self._normalise_headers(df)
        records = self._parse_rows(df, tds_type)
        logger.info(f"Parsed {len(records)} deductee records from {file_path}")
        return records

    def extract_to_json(
        self, file_path: str | Path, tds_type: str = "salary"
    ) -> list[dict]:
        return [r.model_dump(mode="json") for r in self.extract(file_path, tds_type)]

    # ----------------------------------------------------------------- private

    def _load(self, file_path: str | Path) -> pd.DataFrame:
        path = Path(file_path)
        if path.suffix.lower() not in {".xlsx", ".xls", ".xlsm"}:
            raise ValueError(f"Unsupported file type: {path.suffix}")

        # Try each sheet; use the first one with ≥3 columns
        xl = pd.ExcelFile(path)
        for sheet in xl.sheet_names:
            df = pd.read_excel(path, sheet_name=sheet, header=None)
            df = self._find_header_row(df)
            if df is not None and len(df.columns) >= 3:
                logger.debug(f"Using sheet: {sheet!r}")
                return df
        raise ValueError("No usable sheet found in the Excel file")

    def _find_header_row(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """Detect the real header row (first row containing 'PAN' or 'Name')."""
        for idx, row in df.iterrows():
            row_str = " ".join(str(v).lower() for v in row if pd.notna(v))
            if "pan" in row_str or "name" in row_str:
                new_df = df.iloc[int(idx) + 1 :].copy()
                new_df.columns = [str(v).strip() for v in df.iloc[int(idx)]]
                new_df = new_df.reset_index(drop=True)
                new_df = new_df.dropna(how="all")
                return new_df
        return None

    def _normalise_headers(self, df: pd.DataFrame) -> pd.DataFrame:
        """Rename Excel columns to canonical field names."""
        mapping: dict[str, str] = {}
        for canonical, aliases in _COMMON_ALIASES.items():
            for col in df.columns:
                if str(col).strip().lower() in aliases:
                    mapping[col] = canonical
                    break
        return df.rename(columns=mapping)

    def _parse_rows(
        self, df: pd.DataFrame, tds_type: str
    ) -> list[DeducteeRecord]:
        default_section = _TDS_TYPE_SECTION_DEFAULT.get(tds_type, "92B")
        records: list[DeducteeRecord] = []
        serial = 1

        for _, row in df.iterrows():
            pan = self._str(row.get("pan"))
            if not pan or len(pan) != 10:
                continue  # skip rows without a valid PAN

            try:
                record = DeducteeRecord(
                    serial_no=int(self._num(row.get("serial_no")) or serial),
                    pan=pan.upper(),
                    name=self._str(row.get("name")) or "",
                    amount_paid=self._decimal(row.get("amount_paid")),
                    tds_deducted=self._decimal(row.get("tds_deducted")),
                    surcharge=self._decimal(row.get("surcharge")),
                    education_cess=self._decimal(row.get("education_cess")),
                    section=self._str(row.get("section")) or default_section,
                    deductee_type=self._deductee_type(row.get("deductee_type")),
                    lower_deduction_reason=self._lower_deduction_reason(
                        row.get("lower_deduction_reason")
                    ),
                    payment_date=self._parse_date(row.get("payment_date")),
                    credit_date=self._parse_date(row.get("credit_date")),
                    certificate_no=self._str(row.get("certificate_no")),
                    certificate_date=self._parse_date(row.get("certificate_date")),
                    employee_ref_no=self._str(row.get("employee_ref_no")),
                )
                records.append(record)
                serial += 1
            except Exception as exc:
                logger.warning(f"Skipping row (PAN={pan}): {exc}")

        return records

    def _all_rows_to_json(self, df: pd.DataFrame) -> list[dict]:
        """Emit every column for every valid row (PAN present, 10 chars)."""
        # Build a snake_case name for every column (mapped ones already are)
        col_keys = {col: _col_to_snake(col) for col in df.columns}
        records: list[dict] = []
        serial = 1

        for _, row in df.iterrows():
            pan = self._str(row.get("pan"))
            if not pan or len(pan) != 10:
                continue

            record: dict = {"serial_no": int(self._num(row.get("serial_no")) or serial)}

            for col, key in col_keys.items():
                val = row[col]
                if isinstance(val, float) and pd.isna(val):
                    record[key] = None
                elif isinstance(val, (int, float)):
                    record[key] = val
                else:
                    record[key] = self._str(val)

            # section is left null — populated in the next processing step
            record["section"] = self._str(row.get("section")) or None

            records.append(record)
            serial += 1

        logger.info(f"Extracted {len(records)} rows with all columns")
        return records

    # ---------------------------------------------------------------- helpers

    _DATE_FORMATS = ["%d-%m-%Y", "%d/%m/%Y", "%d-%b-%Y", "%d.%m.%Y", "%Y-%m-%d"]

    def _parse_date(self, val) -> Optional[date]:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        if isinstance(val, (datetime,)):
            return val.date()
        if isinstance(val, date):
            return val
        s = str(val).strip()
        for fmt in self._DATE_FORMATS:
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        logger.warning(f"Could not parse date: {val!r}")
        return None

    def _deductee_type(self, val) -> DeducteeType:
        s = (self._str(val) or "").strip().upper()
        if s in ("S", "SENIOR", "SENIOR CITIZEN"):
            return DeducteeType.SENIOR_CITIZEN
        return DeducteeType.ORDINARY

    def _lower_deduction_reason(self, val) -> LowerDeductionReason:
        s = (self._str(val) or "").strip().upper()
        mapping = {
            "A": LowerDeductionReason.LOWER_DEDUCTION_CERTIFICATE,
            "B": LowerDeductionReason.NO_DEDUCTION_CERTIFICATE,
            "C": LowerDeductionReason.THRESHOLD_NOT_REACHED,
            "Y": LowerDeductionReason.VALID_15G_15H,
            "T": LowerDeductionReason.TRANSPORTER,
        }
        return mapping.get(s, LowerDeductionReason.NONE)

    def _str(self, val) -> Optional[str]:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        return str(val).strip()

    def _num(self, val) -> Optional[float]:
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    def _decimal(self, val) -> Decimal:
        raw = self._num(val)
        if raw is None:
            return Decimal("0")
        try:
            return Decimal(str(raw)).quantize(Decimal("0.01"))
        except InvalidOperation:
            return Decimal("0")
