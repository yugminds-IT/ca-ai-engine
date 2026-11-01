"""
Extract structured data from Income Tax Department challan receipt PDFs (ITNS 281).

Uses PyMuPDF (fitz) page.get_text() for embedded text extraction with dynamic
key-value parsing — no hard-coded field patterns.

Output format: {document, fields, tax_breakup}
"""

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
from loguru import logger

from features.tds.schemas.challan import ChallanData


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_amount(value: str) -> str:
    return value.strip().lstrip("₹").strip()


def _to_snake_key(label: str) -> str:
    """'Bank Reference Number' → 'bank_reference_number'"""
    return re.sub(r"[^a-zA-Z0-9]+", "_", label.strip()).strip("_").lower()


def _extract_fields(lines: list[str]) -> dict[str, str]:
    """
    Dynamically extract every key-value pair from the PDF text lines.

    Handles two layouts the ITNS 281 PDF uses:
      1. Single-line:  "ITNS No. : 281"
      2. Three-line:   "Label"  /  ":"  /  "value"
    """
    fields: dict[str, str] = {}
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()

        # Single-line: "Some Label : Some Value"
        if ":" in stripped and not stripped.startswith("₹") and stripped != ":":
            parts = stripped.split(":", 1)
            key, value = parts[0].strip(), parts[1].strip()
            if key and value and len(key.split()) <= 6:
                fields[key] = value
                i += 1
                continue

        # Three-line: line[i] = label, line[i+1] = ":", line[i+2] = value
        if (
            i + 2 < len(lines)
            and lines[i + 1].strip() == ":"
            and stripped
            and not stripped.startswith("₹")
            and len(stripped.split()) <= 6
        ):
            key = stripped
            value = lines[i + 2].strip()
            if value and value != ":":
                fields[key] = value
            i += 3
            continue

        i += 1

    return fields


def _extract_tax_breakup(lines: list[str]) -> dict[str, str]:
    """
    Extract the tax breakup table that appears after 'Tax Breakup Details'.

    Row layout inside that section:
        A              ← single capital letter
        Tax            ← label
        ₹ 26,130       ← amount
        ...
        Total (A+B+C+D+E+F)
        ₹ 26,923
        Total (In Words)
        Rupees ...
    """
    breakup: dict[str, str] = {}
    in_section = False
    i = 0

    while i < len(lines):
        stripped = lines[i].strip()

        if "Tax Breakup Details" in stripped:
            in_section = True
            i += 1
            continue

        if not in_section:
            i += 1
            continue

        # Single capital letter row (A–F) → next two lines are label + amount
        if re.match(r"^[A-Z]$", stripped) and i + 2 < len(lines):
            label = lines[i + 1].strip()
            amount = _clean_amount(lines[i + 2].strip())
            breakup[label] = amount
            i += 3
            continue

        if "Total" in stripped and "Words" not in stripped and i + 1 < len(lines):
            breakup["Total"] = _clean_amount(lines[i + 1].strip())
            i += 2
            continue

        if "Total" in stripped and "Words" in stripped and i + 1 < len(lines):
            breakup["Total (In Words)"] = lines[i + 1].strip()
            i += 2
            continue

        i += 1

    return breakup


# ---------------------------------------------------------------------------
# Extractor class
# ---------------------------------------------------------------------------

class ChallanExtractor:
    DATE_FORMATS = ["%d-%b-%Y", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"]

    # ------------------------------------------------------------------ public

    def extract_to_json(self, file_path: str | Path) -> dict:
        """
        Return structured extraction format:

        {
          "document": {"source_file": "...", "total_pages": 1},
          "fields":   {snake_case_key: raw_string_value, ...},
          "tax_breakup": {"Tax": "26,130", "Surcharge": "0", ...}
        }
        """
        return self._extract_raw(file_path)

    def extract(self, file_path: str | Path) -> ChallanData:
        """Return a typed ChallanData for downstream processors/generators."""
        raw = self._extract_raw(file_path)
        return self._to_challan_data(raw["fields"], raw["tax_breakup"])

    # ----------------------------------------------------------------- private

    def _extract_raw(self, file_path: str | Path) -> dict:
        """Core extraction using fitz embedded text + dynamic key-value parsing."""
        file_path = Path(file_path)
        doc = fitz.open(str(file_path))
        all_lines: list[str] = []

        for page in doc:
            lines = [ln for ln in page.get_text().splitlines() if ln.strip()]
            all_lines.extend(lines)

        logger.debug(f"fitz extracted {len(all_lines)} lines from {file_path.name}")

        raw_fields = _extract_fields(all_lines)
        tax_breakup = _extract_tax_breakup(all_lines)
        fields_out = {_to_snake_key(k): v for k, v in raw_fields.items()}

        return {
            "document": {
                "source_file": file_path.name,
                "total_pages": len(doc),
            },
            "fields": fields_out,
            "tax_breakup": tax_breakup,
        }

    def _to_challan_data(
        self, fields: dict[str, str], breakup: dict[str, str]
    ) -> ChallanData:
        """Map the raw extracted dicts onto the typed ChallanData schema."""

        def _amount(raw: Optional[str]) -> Decimal:
            if not raw:
                return Decimal("0")
            cleaned = re.sub(r"[^\d.]", "", raw)
            try:
                return Decimal(cleaned) if cleaned else Decimal("0")
            except InvalidOperation:
                return Decimal("0")

        def _date(raw: Optional[str]) -> Optional[datetime.date]:
            if not raw:
                return None
            for fmt in self.DATE_FORMATS:
                try:
                    return datetime.strptime(raw.strip(), fmt).date()
                except ValueError:
                    continue
            logger.warning(f"Could not parse date: {raw!r}")
            return None

        # Full strings like "Income Tax (Other than Companies) (0021)" → "0021"
        major_head_raw = fields.get("major_head", "")
        m = re.search(r"\((\d{4})\)", major_head_raw)
        major_head = m.group(1) if m else "0021"

        minor_head_raw = fields.get("minor_head", "")
        m = re.search(r"\((\d{3})\)", minor_head_raw)
        minor_head = m.group(1) if m else "200"

        return ChallanData(
            tan=fields.get("tan", ""),
            deductor_name=fields.get("name", ""),
            assessment_year=fields.get("assessment_year", ""),
            financial_year=fields.get("financial_year", ""),
            major_head=major_head,
            minor_head=minor_head,
            nature_of_payment=fields.get("nature_of_payment", ""),
            cin=fields.get("cin", ""),
            mode_of_payment=fields.get("mode_of_payment", "").strip(),
            bank_name=fields.get("bank_name", "").strip(),
            bank_reference_number=fields.get("bank_reference_number", ""),
            date_of_deposit=_date(fields.get("date_of_deposit")),
            bsr_code=fields.get("bsr_code", ""),
            challan_no=fields.get("challan_no", ""),
            tender_date=_date(fields.get("tender_date")),
            total_amount=_amount(fields.get("amount_in_rs")),
            tax=_amount(breakup.get("Tax")),
            surcharge=_amount(breakup.get("Surcharge")),
            cess=_amount(breakup.get("Cess")),
            interest=_amount(breakup.get("Interest")),
            penalty=_amount(breakup.get("Penalty")),
            fee_234e=_amount(breakup.get("Fee under section 234E")),
        )
