"""Complete TDS/TCS return data structures — one per form type (24Q, 26Q, 27Q, 27EQ, 26QB, 26QC, 26QD, 26QE, 24G)."""

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, computed_field

from features.tds.schemas.challan import ChallanData
from features.tds.schemas.deductee import (
    DeducteeRecord,
    ECommerceRecord,
    GovernmentRecord,
    NonResidentDeducteeRecord,
    PropertyRecord,
    RentRecord,
    SalaryDeducteeRecord,
    TCSRecord,
    VDARecord,
)


# ---------------------------------------------------------------------------
# Deductor metadata — shared by all forms
# ---------------------------------------------------------------------------

class DeductorMeta(BaseModel):
    """Deductor / collector identification block (maps to BH record in FVU)."""

    tan: str
    pan: Optional[str] = None
    name: str
    branch: str = ""

    # Address (up to 5 lines per NSDL spec)
    address_line1: str = ""
    address_line2: str = ""
    address_line3: str = ""
    address_line4: str = ""
    address_line5: str = ""
    pincode: str = ""

    # Contact
    std_code: str = ""
    phone: str = ""
    email: str = ""

    # Responsible person (who signs / submits the return)
    responsible_name: str = ""
    responsible_designation: str = ""
    responsible_pan: str = ""
    responsible_mobile: str = ""
    responsible_email: str = ""

    # Deductor category
    deductor_type: str = "A"        # A=Company, B=Other than company
    is_government: bool = False     # True for central/state govt deductors

    # Government-specific (Form 24G)
    ain: str = ""                   # Account Office Identification Number (govt only)
    pao_code: str = ""              # Pay and Accounts Office code
    ddo_code: str = ""              # Drawing and Disbursing Officer code
    ministry_code: str = ""


# ---------------------------------------------------------------------------
# Challan bundle (used by 24Q, 26Q, 27Q, 27EQ)
# ---------------------------------------------------------------------------

class ChallanWithDeductees(BaseModel):
    challan: ChallanData
    deductees: list[DeducteeRecord] = Field(default_factory=list)

    @computed_field
    @property
    def deductee_count(self) -> int:
        return len(self.deductees)

    @computed_field
    @property
    def total_tds_deducted(self) -> Decimal:
        return sum(d.tds_deducted for d in self.deductees)


class ChallanWithSalaryDeductees(BaseModel):
    challan: ChallanData
    deductees: list[SalaryDeducteeRecord] = Field(default_factory=list)

    @computed_field
    @property
    def deductee_count(self) -> int:
        return len(self.deductees)

    @computed_field
    @property
    def total_tds_deducted(self) -> Decimal:
        return sum(d.tds_deducted for d in self.deductees)


class ChallanWithNRDeductees(BaseModel):
    challan: ChallanData
    deductees: list[NonResidentDeducteeRecord] = Field(default_factory=list)

    @computed_field
    @property
    def deductee_count(self) -> int:
        return len(self.deductees)

    @computed_field
    @property
    def total_tds_deducted(self) -> Decimal:
        return sum(d.tds_deducted for d in self.deductees)


class ChallanWithTCSRecords(BaseModel):
    challan: ChallanData
    records: list[TCSRecord] = Field(default_factory=list)

    @computed_field
    @property
    def record_count(self) -> int:
        return len(self.records)

    @computed_field
    @property
    def total_tcs_collected(self) -> Decimal:
        return sum(r.tcs_collected for r in self.records)


# ---------------------------------------------------------------------------
# Base TDS return
# ---------------------------------------------------------------------------

class TDSReturn(BaseModel):
    form_type: str
    financial_year: str
    quarter: str                    # Q1 / Q2 / Q3 / Q4
    deductor: DeductorMeta
    challans: list[ChallanWithDeductees] = Field(default_factory=list)
    is_correction: bool = False
    previous_rrr_no: Optional[str] = None  # RRR no. of original return (for corrections)

    @computed_field
    @property
    def total_challans(self) -> int:
        return len(self.challans)

    @computed_field
    @property
    def total_tax_deposited(self) -> Decimal:
        return sum(c.challan.total_amount for c in self.challans)

    @computed_field
    @property
    def assessment_year(self) -> str:
        start, _ = self.financial_year.split("-")
        return f"{int(start) + 1}-{str(int(start) + 2)[-2:]}"


# ---------------------------------------------------------------------------
# Form 24Q — TDS on Salary (Section 192 / 92A / 92B)
# ---------------------------------------------------------------------------

class TDSReturn24Q(TDSReturn):
    """
    Form 24Q — Quarterly TDS return for salary payments.
    Filed by all employers. Annexure II (full salary breakup) required only in Q4.
    """
    form_type: str = "24Q"
    challans: list[ChallanWithSalaryDeductees] = Field(default_factory=list)  # type: ignore[assignment]

    @computed_field
    @property
    def total_tax_deposited(self) -> Decimal:
        return sum(c.challan.total_amount for c in self.challans)

    @computed_field
    @property
    def total_challans(self) -> int:
        return len(self.challans)


# ---------------------------------------------------------------------------
# Form 26Q — TDS on Non-Salary Resident Payments
# ---------------------------------------------------------------------------

class TDSReturn26Q(TDSReturn):
    """
    Form 26Q — Quarterly TDS return for non-salary payments to residents.
    Sections: 193, 194, 194A–194S (excluding salary and non-resident).
    """
    form_type: str = "26Q"


# ---------------------------------------------------------------------------
# Form 27Q — TDS on Payments to Non-Residents
# ---------------------------------------------------------------------------

class TDSReturn27Q(BaseModel):
    """
    Form 27Q — Quarterly TDS return for payments to non-residents / foreign companies.
    Sections: 195, 196A, 196B, 196C, 196D, 194E, 194LB, 194LC, 194LD.
    """
    form_type: str = "27Q"
    financial_year: str
    quarter: str
    deductor: DeductorMeta
    challans: list[ChallanWithNRDeductees] = Field(default_factory=list)
    is_correction: bool = False
    previous_rrr_no: Optional[str] = None

    @computed_field
    @property
    def assessment_year(self) -> str:
        start, _ = self.financial_year.split("-")
        return f"{int(start) + 1}-{str(int(start) + 2)[-2:]}"

    @computed_field
    @property
    def total_challans(self) -> int:
        return len(self.challans)

    @computed_field
    @property
    def total_tax_deposited(self) -> Decimal:
        return sum(c.challan.total_amount for c in self.challans)


# ---------------------------------------------------------------------------
# Form 27EQ — TCS (Tax Collected at Source, Section 206C)
# ---------------------------------------------------------------------------

class TCSReturn27EQ(BaseModel):
    """
    Form 27EQ — Quarterly TCS return.
    Filed by sellers/collectors: liquor, timber, scrap, minerals, overseas remittance, etc.
    """
    form_type: str = "27EQ"
    financial_year: str
    quarter: str
    deductor: DeductorMeta          # "Deductor" here is actually the collector
    challans: list[ChallanWithTCSRecords] = Field(default_factory=list)
    is_correction: bool = False
    previous_rrr_no: Optional[str] = None

    @computed_field
    @property
    def assessment_year(self) -> str:
        start, _ = self.financial_year.split("-")
        return f"{int(start) + 1}-{str(int(start) + 2)[-2:]}"

    @computed_field
    @property
    def total_challans(self) -> int:
        return len(self.challans)

    @computed_field
    @property
    def total_tcs_deposited(self) -> Decimal:
        return sum(c.challan.total_amount for c in self.challans)


# ---------------------------------------------------------------------------
# Form 26QB — TDS on purchase of immovable property (Section 194IA)
# ---------------------------------------------------------------------------

class TDSReturn26QB(BaseModel):
    """
    Form 26QB — One-time TDS return per property purchase transaction.
    Filed by buyer; no challan file upload; payment via ITNS 26QB online.
    Rate: 1% on consideration ≥ ₹50 lakh.
    """
    form_type: str = "26QB"
    financial_year: str
    deductor: DeductorMeta          # Buyer acts as deductor
    record: PropertyRecord
    is_correction: bool = False


# ---------------------------------------------------------------------------
# Form 26QC — TDS on rent by Individual/HUF (Section 194IB)
# ---------------------------------------------------------------------------

class TDSReturn26QC(BaseModel):
    """
    Form 26QC — One-time TDS return for rent payments by Individual/HUF.
    Filed by tenant; rate 5% on monthly rent > ₹50,000.
    """
    form_type: str = "26QC"
    financial_year: str
    deductor: DeductorMeta          # Tenant acts as deductor
    record: RentRecord
    is_correction: bool = False


# ---------------------------------------------------------------------------
# Form 26QD — TDS on e-commerce payments (Section 194O)
# ---------------------------------------------------------------------------

class TDSReturn26QD(BaseModel):
    """
    Form 26QD — Quarterly TDS return for e-commerce operators.
    Rate: 1% on gross amount paid/credited to e-commerce participants.
    """
    form_type: str = "26QD"
    financial_year: str
    quarter: str
    deductor: DeductorMeta          # E-commerce operator
    challans: list[ChallanWithDeductees] = Field(default_factory=list)
    ecommerce_records: list[ECommerceRecord] = Field(default_factory=list)
    is_correction: bool = False
    previous_rrr_no: Optional[str] = None

    @computed_field
    @property
    def assessment_year(self) -> str:
        start, _ = self.financial_year.split("-")
        return f"{int(start) + 1}-{str(int(start) + 2)[-2:]}"


# ---------------------------------------------------------------------------
# Form 26QE — TDS on Virtual Digital Assets (Section 194S)
# ---------------------------------------------------------------------------

class TDSReturn26QE(BaseModel):
    """
    Form 26QE — Quarterly TDS return for VDA (crypto/NFT) transfers.
    Rate: 1% on consideration. Filed by specified persons and exchanges.
    """
    form_type: str = "26QE"
    financial_year: str
    quarter: str
    deductor: DeductorMeta
    challans: list[ChallanWithDeductees] = Field(default_factory=list)
    vda_records: list[VDARecord] = Field(default_factory=list)
    is_correction: bool = False
    previous_rrr_no: Optional[str] = None

    @computed_field
    @property
    def assessment_year(self) -> str:
        start, _ = self.financial_year.split("-")
        return f"{int(start) + 1}-{str(int(start) + 2)[-2:]}"


# ---------------------------------------------------------------------------
# Form 24G — TDS/TCS Book Adjustment Statement (Government deductors)
# ---------------------------------------------------------------------------

class TDSReturn24G(BaseModel):
    """
    Form 24G — Monthly book adjustment statement for government deductors.
    Filed by PAO/CDDO/DTO instead of a bank challan. No cash payment involved.
    """
    form_type: str = "24G"
    financial_year: str
    month: str                      # MM format e.g. "04" for April
    deductor: DeductorMeta          # Must have is_government=True and ain set
    records: list[GovernmentRecord] = Field(default_factory=list)
    is_correction: bool = False
    previous_statement_no: Optional[str] = None

    @computed_field
    @property
    def total_tds_tcs(self) -> Decimal:
        return sum(r.tds_tcs_amount for r in self.records)

    @computed_field
    @property
    def total_amount(self) -> Decimal:
        return sum(r.total_amount for r in self.records)
