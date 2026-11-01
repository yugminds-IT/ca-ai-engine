"""
Form 24Q processor — TDS on Salary (Section 192).

Assembles ChallanData + DeducteeRecords into a TDSReturn24Q ready for
CSI/FVU file generation and Annexure I / II preview.
"""

from decimal import Decimal
from typing import Optional

from loguru import logger

from features.tds.schemas.challan import ChallanData
from features.tds.schemas.deductee import DeducteeRecord
from features.tds.schemas.deductee import SalaryDeducteeRecord
from features.tds.schemas.return_file import (
    ChallanWithSalaryDeductees,
    DeductorMeta,
    TDSReturn24Q,
)


class Form24QProcessor:
    """Build and validate Form 24Q return data."""

    def build(
        self,
        challan: ChallanData,
        deductees: list[DeducteeRecord],
        deductor_meta: dict,
        quarter: str = "Q4",
    ) -> TDSReturn24Q:
        deductor = DeductorMeta(**deductor_meta)

        # Renumber and upcast to SalaryDeducteeRecord (adds optional salary fields with defaults)
        renumbered = [
            SalaryDeducteeRecord(**{**d.model_dump(), "serial_no": i + 1})
            for i, d in enumerate(deductees)
        ]

        challan_bundle = ChallanWithSalaryDeductees(
            challan=challan,
            deductees=renumbered,
        )

        self._warn_if_tds_mismatch(challan, renumbered)

        return TDSReturn24Q(
            financial_year=challan.financial_year or deductor_meta.get("financial_year", ""),
            quarter=quarter,
            deductor=deductor,
            challans=[challan_bundle],
        )

    def build_annexure_i(self, return_data: TDSReturn24Q) -> list[dict]:
        """Return rows matching the RPU Annexure I (Deductee Details) layout."""
        rows = []
        for challan_bundle in return_data.challans:
            c = challan_bundle.challan
            for d in challan_bundle.deductees:
                rows.append({
                    "row_number": d.serial_no,
                    "challan_serial_no": 1,
                    "update_mode": "A",
                    "bsr_code": c.bsr_code,
                    "date_tax_deposited": c.challan_deposit_ddmmyyyy(),
                    "transfer_voucher_challan_serial_no": c.challan_no,
                    "section_under_which_payment_made": c.nature_of_payment,
                    "total_tds_allocated": float(c.tax),
                    "interest": float(c.interest),
                    "others": float(c.fee_234e + c.penalty),
                    "total": float(c.total_amount),
                    "sr_no": d.serial_no,
                    "employee_ref_no": d.employee_ref_no or "",
                    "pan": d.pan,
                })
        return rows

    def build_annexure_ii(self, return_data: TDSReturn24Q) -> list[dict]:
        """Return rows for the RPU Annexure II (Salary Details) layout."""
        rows = []
        for challan_bundle in return_data.challans:
            for d in challan_bundle.deductees:
                rows.append({
                    "sr_no": d.serial_no,
                    "pan": d.pan,
                    "name": d.name,
                    "gross_salary": float(d.amount_paid),
                    "tds_deducted": float(d.tds_deducted),
                    "surcharge": float(d.surcharge),
                    "cess": float(d.education_cess),
                    "total_tax": float(d.total_tax or d.tds_deducted),
                    "section": d.section,
                })
        return rows

    # -------------------------------------------------------------- internal

    def _warn_if_tds_mismatch(
        self, challan: ChallanData, deductees: list[DeducteeRecord]
    ) -> None:
        total_deductee_tds = sum(d.tds_deducted for d in deductees)
        if total_deductee_tds != Decimal("0") and abs(total_deductee_tds - challan.tax) > Decimal("1"):
            logger.warning(
                f"TDS mismatch: challan.tax={challan.tax}, "
                f"sum(deductee tds)={total_deductee_tds}"
            )
