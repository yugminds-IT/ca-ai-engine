"""Pydantic model for Income Tax Department challan receipt data (ITNS 281)."""

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class ChallanData(BaseModel):
    # Identification
    itns_no: str = "281"
    tan: str = Field(description="Tax Deduction Account Number (10 chars)")
    deductor_name: str
    assessment_year: str = Field(description="e.g. 2026-27")
    financial_year: str = Field(description="e.g. 2025-26")

    # Head codes
    major_head: str = Field(default="0021", description="0020=Companies, 0021=Others")
    minor_head: str = Field(default="200", description="200=Payable by taxpayer")
    nature_of_payment: str = Field(description="Section code e.g. 92B, 194J, 194I")

    # Payment identifiers
    cin: str = Field(description="Challan Identification Number from bank")
    mode_of_payment: str = "Net Banking"
    bank_name: str = ""
    bank_reference_number: str = ""

    # Dates
    date_of_deposit: Optional[date] = None
    tender_date: Optional[date] = None

    # Bank identifiers
    bsr_code: str = Field(description="7-digit BSR code of bank branch")
    challan_no: str = Field(description="Challan serial number")

    # Tax breakup (amounts in INR)
    tax: Decimal = Decimal("0")
    surcharge: Decimal = Decimal("0")
    cess: Decimal = Decimal("0")
    interest: Decimal = Decimal("0")
    penalty: Decimal = Decimal("0")
    fee_234e: Decimal = Decimal("0")
    total_amount: Decimal = Decimal("0")

    @model_validator(mode="after")
    def compute_total_if_missing(self) -> "ChallanData":
        computed = self.tax + self.surcharge + self.cess + self.interest + self.penalty + self.fee_234e
        if self.total_amount == Decimal("0") and computed > 0:
            self.total_amount = computed
        return self

    def date_ddmmyyyy(self, d: Optional[date]) -> str:
        return d.strftime("%d%m%Y") if d else ""

    def challan_deposit_ddmmyyyy(self) -> str:
        return self.date_ddmmyyyy(self.date_of_deposit or self.tender_date)

    class Config:
        from_attributes = True
