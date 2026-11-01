"""
Form 27Q processor — TDS on payments to Non-Residents.

Sections: 195, 196A, 196B, 196C, 196D, 194E, 194LB, 194LBA, 194LBB, 194LBC, 194LC, 194LD.
"""

from loguru import logger

from features.tds.schemas.challan import ChallanData
from features.tds.schemas.deductee import NonResidentDeducteeRecord
from features.tds.schemas.return_file import (
    ChallanWithNRDeductees,
    DeductorMeta,
    TDSReturn27Q,
)
from features.tds.types.non_resident import SECTIONS


class Form27QProcessor:
    """Build and validate Form 27Q return data."""

    def build(
        self,
        challan: ChallanData,
        deductees: list[NonResidentDeducteeRecord],
        deductor_meta: dict,
        quarter: str = "Q4",
    ) -> TDSReturn27Q:
        section = challan.nature_of_payment
        if section not in SECTIONS:
            logger.warning(f"Section {section!r} not in known 27Q sections; proceeding anyway")

        deductor = DeductorMeta(**deductor_meta)
        renumbered = [
            d.model_copy(update={"serial_no": i + 1})
            for i, d in enumerate(deductees)
        ]

        challan_bundle = ChallanWithNRDeductees(challan=challan, deductees=renumbered)

        return TDSReturn27Q(
            financial_year=challan.financial_year or deductor_meta.get("financial_year", ""),
            quarter=quarter,
            deductor=deductor,
            challans=[challan_bundle],
        )

    def build_annexure_i(self, return_data: TDSReturn27Q) -> list[dict]:
        """Deductee details in RPU Annexure I format for Form 27Q."""
        rows = []
        for bundle in return_data.challans:
            c = bundle.challan
            for d in bundle.deductees:
                rows.append({
                    "row_number": d.serial_no,
                    "challan_serial_no": 1,
                    "bsr_code": c.bsr_code,
                    "date_tax_deposited": c.challan_deposit_ddmmyyyy(),
                    "challan_no": c.challan_no,
                    "section": d.section,
                    "total_tds_allocated": float(c.tax),
                    "interest": float(c.interest),
                    "others": float(c.fee_234e + c.penalty),
                    "total": float(c.total_amount),
                    "sr_no": d.serial_no,
                    "pan": d.pan,
                    "name": d.name,
                    "country_of_residence": d.country_of_residence,
                    "nature_of_remittance": d.nature_of_remittance,
                    "gross_amount_before_tds": float(d.gross_amount_before_tds),
                    "tds_rate_applied": float(d.tds_rate_applied or 0),
                    "tds_deducted": float(d.tds_deducted),
                    "dtaa_applicable": d.dtaa_applicable,
                    "dtaa_article": d.dtaa_article or "",
                    "dtaa_rate": float(d.dtaa_rate or 0),
                    "trc_no": d.tax_residency_certificate_no or "",
                    "form_15ca_ack_no": d.form_15ca_ack_no or "",
                    "form_15cb_cert_no": d.form_15cb_cert_no or "",
                    "remittance_currency": d.remittance_currency,
                    "remittance_amount_foreign_currency": float(d.remittance_amount_foreign_currency),
                    "payment_date": d.date_ddmmyyyy(d.payment_date),
                    "lower_deduction_reason": d.lower_deduction_reason.value,
                    "certificate_no": d.certificate_no or "",
                })
        return rows
