"""
Form 26QB processor — TDS on purchase of immovable property (Section 194IA).

Rate: 1% on sale consideration ≥ ₹50 lakh.
Filed by buyer (not the employer's quarterly return flow — one form per transaction).
"""

from features.tds.schemas.deductee import PropertyRecord
from features.tds.schemas.return_file import DeductorMeta, TDSReturn26QB
from features.tds.types.property import (
    SECTION_194IA,
    THRESHOLD_194IA,
    TDS_RATE_194IA,
    compute_tds_194ia,
)


class Form26QBProcessor:
    """Build and validate Form 26QB return data."""

    def build(
        self,
        record: PropertyRecord,
        deductor_meta: dict,
        financial_year: str,
    ) -> TDSReturn26QB:
        deductor = DeductorMeta(**deductor_meta)
        return TDSReturn26QB(
            financial_year=financial_year,
            deductor=deductor,
            record=record,
        )

    def compute_tds(self, record: PropertyRecord) -> PropertyRecord:
        """Fill in tds_deducted if not already set."""
        if record.tds_deducted == 0 and record.amount_paid_this_installment > 0:
            tds = compute_tds_194ia(record.amount_paid_this_installment)
            record = record.model_copy(update={"tds_deducted": tds, "total_tax": tds})
        return record

    def build_summary(self, return_data: TDSReturn26QB) -> dict:
        r = return_data.record
        return {
            "form_type": return_data.form_type,
            "financial_year": return_data.financial_year,
            "section": SECTION_194IA,
            "tds_rate": float(TDS_RATE_194IA),
            "threshold": float(THRESHOLD_194IA),
            "buyer_pan_1": r.buyer_pan_1,
            "buyer_name_1": r.buyer_name_1,
            "buyer_pan_2": r.buyer_pan_2 or "",
            "buyer_name_2": r.buyer_name_2 or "",
            "seller_pan_1": r.seller_pan_1,
            "seller_name_1": r.seller_name_1,
            "seller_pan_2": r.seller_pan_2 or "",
            "seller_name_2": r.seller_name_2 or "",
            "property_address": r.property_address,
            "property_city": r.property_city,
            "property_state": r.property_state,
            "property_pincode": r.property_pincode,
            "property_type": r.property_type.value,
            "total_value_of_property": float(r.total_value_of_property),
            "amount_paid_this_installment": float(r.amount_paid_this_installment),
            "date_of_agreement": r.date_ddmmyyyy(r.date_of_agreement),
            "date_of_payment": r.date_ddmmyyyy(r.date_of_payment),
            "date_of_deduction": r.date_ddmmyyyy(r.date_of_deduction),
            "mode_of_payment": r.mode_of_payment,
            "tds_deducted": float(r.tds_deducted),
            "surcharge": float(r.surcharge),
            "education_cess": float(r.education_cess),
            "total_tax": float(r.total_tax),
        }
