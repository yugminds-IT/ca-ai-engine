"""
Form 27EQ processor — Tax Collected at Source (TCS, Section 206C).

Covers all sub-sections of 206C: liquor, timber, scrap, minerals, motor vehicles,
LRS remittances, sale of goods > ₹50 lakh, etc.
"""

from loguru import logger

from features.tds.schemas.challan import ChallanData
from features.tds.schemas.deductee import TCSRecord
from features.tds.schemas.return_file import (
    ChallanWithTCSRecords,
    DeductorMeta,
    TCSReturn27EQ,
)
from features.tds.types.tcs import SUBSECTIONS


class Form27EQProcessor:
    """Build and validate Form 27EQ TCS return data."""

    def build(
        self,
        challan: ChallanData,
        records: list[TCSRecord],
        deductor_meta: dict,
        quarter: str = "Q4",
    ) -> TCSReturn27EQ:
        section = challan.nature_of_payment
        if section not in SUBSECTIONS and section != "206C":
            logger.warning(f"Section {section!r} not in known 27EQ sub-sections; proceeding anyway")

        deductor = DeductorMeta(**deductor_meta)
        renumbered = [
            r.model_copy(update={"serial_no": i + 1})
            for i, r in enumerate(records)
        ]

        challan_bundle = ChallanWithTCSRecords(challan=challan, records=renumbered)

        return TCSReturn27EQ(
            financial_year=challan.financial_year or deductor_meta.get("financial_year", ""),
            quarter=quarter,
            deductor=deductor,
            challans=[challan_bundle],
        )

    def build_annexure_i(self, return_data: TCSReturn27EQ) -> list[dict]:
        """TCS party details in RPU Annexure I format for Form 27EQ."""
        rows = []
        for bundle in return_data.challans:
            c = bundle.challan
            for r in bundle.records:
                rows.append({
                    "row_number": r.serial_no,
                    "challan_serial_no": 1,
                    "bsr_code": c.bsr_code,
                    "date_tax_deposited": c.challan_deposit_ddmmyyyy(),
                    "challan_no": c.challan_no,
                    "section_206c": r.section_206c,
                    "total_tcs_allocated": float(c.tax),
                    "interest": float(c.interest),
                    "others": float(c.fee_234e + c.penalty),
                    "total": float(c.total_amount),
                    "sr_no": r.serial_no,
                    "buyer_pan": r.buyer_pan,
                    "buyer_name": r.buyer_name,
                    "buyer_type": r.buyer_type,
                    "nature_of_goods_or_services": r.nature_of_goods_or_services,
                    "amount_collected": float(r.amount_collected),
                    "tcs_rate": float(r.tcs_rate),
                    "tcs_collected": float(r.tcs_collected),
                    "surcharge": float(r.surcharge),
                    "education_cess": float(r.education_cess),
                    "total_tcs": float(r.total_tcs),
                    "date_of_collection": r.date_ddmmyyyy(r.date_of_collection),
                    "lower_tcs_reason": r.lower_tcs_reason.value,
                    "certificate_no": r.certificate_no or "",
                    "higher_tcs_applicable": r.higher_tcs_applicable,
                    "last_pan_used": r.last_pan_used or r.buyer_pan,
                })
        return rows
