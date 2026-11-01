"""Business-rule validation for TDS return data before file generation."""

import re
from dataclasses import dataclass, field
from decimal import Decimal

from features.tds.schemas.challan import ChallanData
from features.tds.schemas.deductee import DeducteeRecord
from features.tds.schemas.return_file import TDSReturn


@dataclass
class ValidationResult:
    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.is_valid = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


_PAN_RE = re.compile(r"^[A-Z]{5}\d{4}[A-Z]$")
_TAN_RE = re.compile(r"^[A-Z]{4}\d{5}[A-Z]$")
_BSR_RE = re.compile(r"^\d{7}$")


class TDSValidator:

    def validate_return(self, return_data: TDSReturn) -> ValidationResult:
        result = ValidationResult()

        self._check_deductor(return_data.deductor, result)

        if not return_data.challans:
            result.add_error("No challans found in return data")

        for i, bundle in enumerate(return_data.challans, start=1):
            self._check_challan(bundle.challan, i, result)
            if not bundle.deductees:
                result.add_warning(f"Challan {i}: no deductees")
            for j, d in enumerate(bundle.deductees, start=1):
                self._check_deductee(d, j, result)

        return result

    def validate_challan(self, challan: ChallanData) -> ValidationResult:
        result = ValidationResult()
        self._check_challan(challan, 1, result)
        return result

    # ----------------------------------------------------------------- checks

    def _check_deductor(self, deductor, result: ValidationResult) -> None:
        if not _TAN_RE.match(deductor.tan or ""):
            result.add_error(f"Invalid TAN: {deductor.tan!r}")
        if not deductor.name:
            result.add_error("Deductor name is required")

    def _check_challan(
        self, challan: ChallanData, idx: int, result: ValidationResult
    ) -> None:
        prefix = f"Challan {idx}"

        if not _BSR_RE.match(challan.bsr_code or ""):
            result.add_error(f"{prefix}: BSR code must be 7 digits, got {challan.bsr_code!r}")

        if not challan.challan_no:
            result.add_error(f"{prefix}: Challan number is required")

        if challan.total_amount <= Decimal("0"):
            result.add_error(f"{prefix}: Total amount must be > 0")

        computed = challan.tax + challan.surcharge + challan.cess + challan.interest + challan.penalty + challan.fee_234e
        if abs(computed - challan.total_amount) > Decimal("1"):
            result.add_warning(
                f"{prefix}: Breakup sum ({computed}) differs from total ({challan.total_amount})"
            )

        if challan.date_of_deposit is None and challan.tender_date is None:
            result.add_error(f"{prefix}: Date of deposit is required")

    def _check_deductee(
        self, d: DeducteeRecord, idx: int, result: ValidationResult
    ) -> None:
        prefix = f"Deductee {idx} (PAN {d.pan})"

        if not _PAN_RE.match(d.pan or ""):
            result.add_error(f"{prefix}: Invalid PAN format")

        if not d.name:
            result.add_warning(f"{prefix}: Name is missing")

        if d.tds_deducted < Decimal("0"):
            result.add_error(f"{prefix}: TDS deducted cannot be negative")
