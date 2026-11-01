"""Pydantic models for GST invoice extraction."""

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, computed_field


class ValidationStatus(str, Enum):
    ok = "ok"
    review = "review"
    error = "error"


class InvoiceData(BaseModel):
    """Raw extracted fields from a single GST invoice page."""

    gstin: str = Field(default="", description="15-char GSTIN of the supplier")
    invoice_no: str = Field(default="", description="Invoice number")
    invoice_date: str = Field(default="", description="Invoice date DD-MM-YYYY")
    party_name: str = Field(default="", description="Supplier / vendor name")
    taxable_value: Decimal = Field(default=Decimal("0"), description="Taxable amount (₹)")
    cgst: Decimal = Field(default=Decimal("0"), description="Central GST (₹)")
    sgst: Decimal = Field(default=Decimal("0"), description="State GST (₹)")
    igst: Decimal = Field(default=Decimal("0"), description="Integrated GST (₹)")
    total: Decimal = Field(default=Decimal("0"), description="Invoice total (₹)")
    source_file: str = Field(default="", description="Source file name")
    page_no: int = Field(default=1, description="Page number within file")

    class Config:
        from_attributes = True


class ValidationResult(BaseModel):
    """Validation outcome for one invoice."""

    status: ValidationStatus = ValidationStatus.ok
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    gstin_valid: bool = True
    tax_sum_valid: bool = True


class InvoiceRecord(BaseModel):
    """Single invoice data + its validation results."""

    invoice: InvoiceData
    validation: ValidationResult


class ExtractionResult(BaseModel):
    """Top-level result for a single processed file."""

    source_file: str
    total_pages: int
    total_invoices: int
    records: list[InvoiceRecord] = Field(default_factory=list)

    @computed_field
    @property
    def error_count(self) -> int:
        return sum(1 for r in self.records if r.validation.status == ValidationStatus.error)

    @computed_field
    @property
    def review_count(self) -> int:
        return sum(1 for r in self.records if r.validation.status == ValidationStatus.review)

    @computed_field
    @property
    def ok_count(self) -> int:
        return sum(1 for r in self.records if r.validation.status == ValidationStatus.ok)
