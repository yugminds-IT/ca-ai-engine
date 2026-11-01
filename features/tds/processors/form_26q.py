"""
Form 26Q processor — TDS on Non-Salary payments.

Covers:
  • Professional Income  — Section 194J
  • Rent                 — Section 194I / 194IB
  • Contractor payments  — Section 194C
"""

from loguru import logger

from features.tds.schemas.challan import ChallanData
from features.tds.schemas.deductee import DeducteeRecord
from features.tds.schemas.return_file import (
    ChallanWithDeductees,
    DeductorMeta,
    TDSReturn26Q,
)

# Sections applicable to Form 26Q
FORM_26Q_SECTIONS = {
    "194J": "Professional / Technical fees",
    "194I": "Rent (plant/machinery/land/building)",
    "194IB": "Rent by Individual/HUF (monthly > 50k)",
    "194C": "Contractor / sub-contractor",
    "194H": "Commission / brokerage",
    "194A": "Interest (other than securities)",
    "194D": "Insurance commission",
}


class Form26QProcessor:
    """Build and validate Form 26Q return data."""

    def build(
        self,
        challan: ChallanData,
        deductees: list[DeducteeRecord],
        deductor_meta: dict,
        quarter: str = "Q4",
    ) -> TDSReturn26Q:
        section = challan.nature_of_payment
        if section not in FORM_26Q_SECTIONS:
            logger.warning(
                f"Section {section!r} not in known 26Q sections; proceeding anyway"
            )

        deductor = DeductorMeta(**deductor_meta)
        renumbered = [
            d.model_copy(update={"serial_no": i + 1, "section": d.section or section})
            for i, d in enumerate(deductees)
        ]

        challan_bundle = ChallanWithDeductees(
            challan=challan,
            deductees=renumbered,
        )

        return TDSReturn26Q(
            financial_year=challan.financial_year or deductor_meta.get("financial_year", ""),
            quarter=quarter,
            deductor=deductor,
            challans=[challan_bundle],
        )

    def build_annexure_i(self, return_data: TDSReturn26Q) -> list[dict]:
        """Deductee details in RPU Annexure I format for Form 26Q."""
        rows = []
        for challan_bundle in return_data.challans:
            c = challan_bundle.challan
            for d in challan_bundle.deductees:
                rows.append({
                    "row_number": d.serial_no,
                    "challan_serial_no": 1,
                    "bsr_code": c.bsr_code,
                    "date_tax_deposited": c.challan_deposit_ddmmyyyy(),
                    "challan_no": c.challan_no,
                    "section": d.section or c.nature_of_payment,
                    "total_tds_allocated": float(c.tax),
                    "interest": float(c.interest),
                    "others": float(c.fee_234e + c.penalty),
                    "total": float(c.total_amount),
                    "sr_no": d.serial_no,
                    "pan": d.pan,
                    "name": d.name,
                    "amount_paid": float(d.amount_paid),
                    "tds_deducted": float(d.tds_deducted),
                })
        return rows
