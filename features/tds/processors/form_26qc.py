"""
Form 26QC processor — TDS on rent by Individual/HUF (Section 194IB).

Rate: 5% on last month's rent where monthly rent > ₹50,000.
Filed once a year (or on vacating) by the tenant.
"""

from features.tds.schemas.deductee import RentRecord
from features.tds.schemas.return_file import DeductorMeta, TDSReturn26QC
from features.tds.types.property import (
    SECTION_194IB,
    THRESHOLD_194IB_MONTHLY,
    TDS_RATE_194IB,
    compute_tds_194ib,
)


class Form26QCProcessor:
    """Build and validate Form 26QC return data."""

    def build(
        self,
        record: RentRecord,
        deductor_meta: dict,
        financial_year: str,
    ) -> TDSReturn26QC:
        deductor = DeductorMeta(**deductor_meta)
        return TDSReturn26QC(
            financial_year=financial_year,
            deductor=deductor,
            record=record,
        )

    def compute_tds(self, record: RentRecord) -> RentRecord:
        """Fill in tds_deducted on last month's rent if not already set."""
        if record.tds_deducted == 0 and record.monthly_rent > 0:
            tds = compute_tds_194ib(record.last_month_rent or record.monthly_rent)
            record = record.model_copy(update={"tds_deducted": tds, "total_tax": tds})
        return record

    def build_summary(self, return_data: TDSReturn26QC) -> dict:
        r = return_data.record
        return {
            "form_type": return_data.form_type,
            "financial_year": return_data.financial_year,
            "section": SECTION_194IB,
            "tds_rate": float(TDS_RATE_194IB),
            "threshold_monthly": float(THRESHOLD_194IB_MONTHLY),
            "tenant_pan": r.tenant_pan,
            "tenant_name": r.tenant_name,
            "landlord_pan": r.landlord_pan,
            "landlord_name": r.landlord_name,
            "landlord_address": r.landlord_address,
            "property_address": r.property_address,
            "property_type": r.property_type.value,
            "from_date": r.date_ddmmyyyy(r.from_date),
            "to_date": r.date_ddmmyyyy(r.to_date),
            "monthly_rent": float(r.monthly_rent),
            "last_month_rent": float(r.last_month_rent),
            "total_rent_paid": float(r.total_rent_paid),
            "tds_deducted": float(r.tds_deducted),
            "date_of_deduction": r.date_ddmmyyyy(r.date_of_deduction),
            "date_of_deposit": r.date_ddmmyyyy(r.date_of_deposit),
            "surcharge": float(r.surcharge),
            "education_cess": float(r.education_cess),
            "total_tax": float(r.total_tax),
        }
