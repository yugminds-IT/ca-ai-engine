"""
Form 26QD processor — TDS on e-commerce payments (Section 194O).

Rate: 1% on gross amount paid/credited to e-commerce participants.
Filed quarterly by e-commerce operators.
"""

from loguru import logger

from features.tds.schemas.challan import ChallanData
from features.tds.schemas.deductee import ECommerceRecord
from features.tds.schemas.return_file import (
    ChallanWithDeductees,
    DeductorMeta,
    TDSReturn26QD,
)
from features.tds.types.ecommerce import SECTION_194O, TDS_RATE_194O, compute_tds_194o


class Form26QDProcessor:
    """Build and validate Form 26QD return data."""

    def build(
        self,
        challan: ChallanData,
        records: list[ECommerceRecord],
        deductor_meta: dict,
        quarter: str = "Q4",
    ) -> TDSReturn26QD:
        deductor = DeductorMeta(**deductor_meta)
        renumbered = [
            r.model_copy(update={"serial_no": i + 1})
            for i, r in enumerate(records)
        ]

        return TDSReturn26QD(
            financial_year=challan.financial_year or deductor_meta.get("financial_year", ""),
            quarter=quarter,
            deductor=deductor,
            ecommerce_records=renumbered,
        )

    def compute_tds_for_records(
        self, records: list[ECommerceRecord]
    ) -> list[ECommerceRecord]:
        """Fill in tds_deducted for records where it is zero."""
        result = []
        for r in records:
            if r.tds_deducted == 0 and r.gross_amount > 0:
                tds = compute_tds_194o(r.gross_amount)
                r = r.model_copy(update={"tds_deducted": tds, "total_tax": tds})
            result.append(r)
        return result

    def build_annexure_i(self, return_data: TDSReturn26QD) -> list[dict]:
        rows = []
        for i, r in enumerate(return_data.ecommerce_records, start=1):
            rows.append({
                "sr_no": i,
                "section": SECTION_194O,
                "tds_rate": float(TDS_RATE_194O),
                "participant_pan": r.participant_pan,
                "participant_name": r.participant_name,
                "participant_type": r.participant_type,
                "nature_of_services_goods": r.nature_of_services_goods,
                "gross_amount": float(r.gross_amount),
                "tds_deducted": float(r.tds_deducted),
                "surcharge": float(r.surcharge),
                "education_cess": float(r.education_cess),
                "total_tax": float(r.total_tax),
                "date_of_credit_or_payment": r.date_ddmmyyyy(r.date_of_credit_or_payment),
                "lower_deduction_reason": r.lower_deduction_reason.value,
                "certificate_no": r.certificate_no or "",
            })
        return rows
