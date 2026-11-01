"""
Form 24G processor — TDS/TCS Book Adjustment Statement for Government deductors.

Filed monthly by PAO (Pay and Accounts Office) / CDDO / DTO.
No bank challan — TDS transferred via book entry.
"""

from loguru import logger

from features.tds.schemas.deductee import GovernmentRecord
from features.tds.schemas.return_file import DeductorMeta, TDSReturn24G
from features.tds.types.government import GOVT_SECTIONS, validate_ain


class Form24GProcessor:
    """Build and validate Form 24G monthly book adjustment return."""

    def build(
        self,
        records: list[GovernmentRecord],
        deductor_meta: dict,
        financial_year: str,
        month: str,
    ) -> TDSReturn24G:
        deductor = DeductorMeta(**deductor_meta)

        if not deductor.is_government:
            logger.warning("Form 24G is only for government deductors; is_government should be True")

        if deductor.ain and not validate_ain(deductor.ain):
            logger.warning(f"AIN {deductor.ain!r} is not a valid 7-digit code")

        renumbered = [
            r.model_copy(update={"serial_no": i + 1})
            for i, r in enumerate(records)
        ]

        return TDSReturn24G(
            financial_year=financial_year,
            month=month,
            deductor=deductor,
            records=renumbered,
        )

    def build_statement_rows(self, return_data: TDSReturn24G) -> list[dict]:
        """Return rows in the 24G statement format (one row per section/nature)."""
        rows = []
        for r in return_data.records:
            rows.append({
                "serial_no": r.serial_no,
                "section": r.section,
                "section_description": GOVT_SECTIONS.get(r.section, ""),
                "minor_head": r.minor_head,
                "nature_of_payment": r.nature_of_payment,
                "amount_transferred": float(r.amount_transferred),
                "tds_tcs_amount": float(r.tds_tcs_amount),
                "surcharge": float(r.surcharge),
                "education_cess": float(r.education_cess),
                "interest": float(r.interest),
                "penalty": float(r.penalty),
                "total_amount": float(r.total_amount),
                "date_of_transfer": r.date_ddmmyyyy(r.date_of_transfer),
                "transfer_voucher_no": r.transfer_voucher_no or "",
                "ddo_pan": r.ddo_pan or "",
                "ddo_name": r.ddo_name,
                "ddo_designation": r.ddo_designation,
                "ministry_code": r.ministry_code,
                "pay_accounts_code": r.pay_accounts_code,
                "ddo_code": r.ddo_code,
            })
        return rows

    def build_header(self, return_data: TDSReturn24G) -> dict:
        d = return_data.deductor
        return {
            "form_type": return_data.form_type,
            "financial_year": return_data.financial_year,
            "month": return_data.month,
            "ain": d.ain,
            "tan": d.tan,
            "name": d.name,
            "pao_code": d.pao_code,
            "ddo_code": d.ddo_code,
            "ministry_code": d.ministry_code,
            "total_tds_tcs": float(return_data.total_tds_tcs),
            "total_amount": float(return_data.total_amount),
            "record_count": len(return_data.records),
            "is_correction": return_data.is_correction,
        }
