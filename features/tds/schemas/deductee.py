"""Pydantic models for TDS/TCS deductee records — all forms (24Q, 26Q, 27Q, 27EQ, 26QB, 26QC, 26QD, 26QE, 24G)."""

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Shared enums
# ---------------------------------------------------------------------------

class DeducteeType(str, Enum):
    ORDINARY = "O"
    SENIOR_CITIZEN = "S"


class LowerDeductionReason(str, Enum):
    NONE = ""
    LOWER_DEDUCTION_CERTIFICATE = "A"      # Certificate u/s 197
    NO_DEDUCTION_CERTIFICATE = "B"         # Certificate u/s 197A
    THRESHOLD_NOT_REACHED = "C"            # Amount below threshold
    VALID_15G_15H = "Y"                    # Valid Form 15G/15H
    TRANSPORTER = "T"                      # Transporter with valid PAN (194C)


class SalarySection(str, Enum):
    SAME_EMPLOYER = "92A"
    PREVIOUS_EMPLOYER = "92B"


class TaxRegime(str, Enum):
    NEW = "N"
    OLD = "O"


class PropertyType(str, Enum):
    RESIDENTIAL = "R"
    COMMERCIAL = "C"
    LAND = "L"


# ---------------------------------------------------------------------------
# Base deductee record — Form 24Q and 26Q
# ---------------------------------------------------------------------------

class DeducteeRecord(BaseModel):
    """Common deductee record for Form 24Q (salary) and 26Q (non-salary resident)."""

    serial_no: int = Field(ge=1)
    pan: str = Field(description="10-char PAN of employee/deductee")
    name: str

    # Amounts (INR)
    amount_paid: Decimal = Field(default=Decimal("0"), description="Gross salary / amount paid or credited")
    tds_deducted: Decimal = Field(default=Decimal("0"), description="TDS deducted this quarter")
    surcharge: Decimal = Decimal("0")
    education_cess: Decimal = Decimal("0")
    total_tax: Decimal = Decimal("0")

    # Dates
    payment_date: Optional[date] = None
    credit_date: Optional[date] = None

    # Classification
    deductee_type: DeducteeType = DeducteeType.ORDINARY
    section: str = "92B"

    # Lower / nil deduction
    lower_deduction_reason: LowerDeductionReason = LowerDeductionReason.NONE
    certificate_no: Optional[str] = None
    certificate_date: Optional[date] = None

    # Reference
    last_pan_used: Optional[str] = None
    employee_ref_no: Optional[str] = None  # RPU column 314 / employer employee ID

    @field_validator("pan")
    @classmethod
    def validate_pan(cls, v: str) -> str:
        v = v.strip().upper()
        if len(v) != 10:
            raise ValueError(f"PAN must be 10 characters, got: {v!r}")
        return v

    def date_ddmmyyyy(self, d: Optional[date]) -> str:
        return d.strftime("%d%m%Y") if d else ""

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Form 24Q — Salary (Section 192 / 92A / 92B)
# ---------------------------------------------------------------------------

class SalaryDeducteeRecord(DeducteeRecord):
    """Form 24Q — Full salary breakup per employee (Annexure I + II)."""

    section: str = "92B"
    tax_regime: TaxRegime = TaxRegime.NEW

    # --- Gross salary components (Section 17) ---
    salary_u_s_17_1: Decimal = Decimal("0")           # Basic salary, DA, bonus, commission u/s 17(1)
    perquisites_u_s_17_2: Decimal = Decimal("0")      # Perquisites u/s 17(2)
    profit_in_lieu_u_s_17_3: Decimal = Decimal("0")   # Profit in lieu of salary u/s 17(3)
    total_gross_salary: Decimal = Decimal("0")         # 17(1) + 17(2) + 17(3)

    # --- Deductions from salary (Section 16) ---
    entertainment_allowance_deduction: Decimal = Decimal("0")   # 16(ii) — govt employees only
    professional_tax: Decimal = Decimal("0")                    # 16(iii)

    # --- Exemptions u/s 10 ---
    hra_exemption: Decimal = Decimal("0")            # 10(13A) — House Rent Allowance
    lta_exemption: Decimal = Decimal("0")            # 10(5)  — Leave Travel Allowance
    gratuity_exemption: Decimal = Decimal("0")       # 10(10) — Gratuity
    leave_encashment_exemption: Decimal = Decimal("0")  # 10(10AA)
    other_exemptions_10: Decimal = Decimal("0")      # Other exemptions u/s 10
    total_exemptions_10: Decimal = Decimal("0")

    # --- Income computation ---
    standard_deduction_16ia: Decimal = Decimal("75000")   # u/s 16(ia) — FY 2025-26
    net_salary_taxable: Decimal = Decimal("0")             # After Section 16 & Section 10 exemptions
    other_income_reported: Decimal = Decimal("0")          # House property / other sources (employee reported)
    gross_total_income: Decimal = Decimal("0")

    # --- Chapter VI-A deductions ---
    deduction_80c: Decimal = Decimal("0")       # LIC, PF, PPF, ELSS, tuition fees, housing loan principal (max 1.5L)
    deduction_80ccc: Decimal = Decimal("0")     # Pension fund contribution
    deduction_80ccd_1: Decimal = Decimal("0")   # NPS — employee own contribution (within 80C limit)
    deduction_80ccd_1b: Decimal = Decimal("0")  # NPS — additional ₹50,000 u/s 80CCD(1B)
    deduction_80ccd_2: Decimal = Decimal("0")   # NPS — employer contribution (no max cap)
    deduction_80d: Decimal = Decimal("0")       # Health insurance premium (self + parents)
    deduction_80dd: Decimal = Decimal("0")      # Disability of dependent (₹75k / ₹1.25L)
    deduction_80ddb: Decimal = Decimal("0")     # Medical treatment of specified disease
    deduction_80e: Decimal = Decimal("0")       # Education loan interest (no cap)
    deduction_80ee: Decimal = Decimal("0")      # Housing loan interest — first-time buyer (max ₹50k)
    deduction_80eea: Decimal = Decimal("0")     # Housing loan interest — affordable housing (max ₹1.5L)
    deduction_80g: Decimal = Decimal("0")       # Donations to approved funds/institutions
    deduction_80gg: Decimal = Decimal("0")      # Rent paid (when no HRA; max ₹5k/month)
    deduction_80ggc: Decimal = Decimal("0")     # Donation to political parties
    deduction_80tta: Decimal = Decimal("0")     # Savings bank interest — non-senior (max ₹10k)
    deduction_80ttb: Decimal = Decimal("0")     # Interest on deposits — senior citizen (max ₹50k)
    deduction_80u: Decimal = Decimal("0")       # Self disability (₹75k / ₹1.25L)
    total_deductions_vi_a: Decimal = Decimal("0")

    # --- Final tax computation ---
    total_income: Decimal = Decimal("0")             # Gross total income − VI-A deductions
    tax_on_total_income: Decimal = Decimal("0")      # As per slab rates
    rebate_87a: Decimal = Decimal("0")               # Rebate u/s 87A (max ₹25k new / ₹12.5k old regime)
    tax_after_rebate: Decimal = Decimal("0")
    surcharge_on_tax: Decimal = Decimal("0")         # Surcharge on income tax
    health_education_cess: Decimal = Decimal("0")    # 4% cess
    tax_payable: Decimal = Decimal("0")
    relief_89: Decimal = Decimal("0")               # Relief u/s 89 (arrear salary)
    net_tax_payable: Decimal = Decimal("0")

    # --- TDS history across quarters ---
    tds_by_previous_employer: Decimal = Decimal("0")  # TDS deducted by previous employer (92A)
    tds_q1: Decimal = Decimal("0")
    tds_q2: Decimal = Decimal("0")
    tds_q3: Decimal = Decimal("0")
    tds_q4: Decimal = Decimal("0")
    tds_total: Decimal = Decimal("0")               # Total TDS across all quarters + previous employer


# ---------------------------------------------------------------------------
# Form 26Q — Non-Salary Resident (Sections 193–194S excluding salary)
# ---------------------------------------------------------------------------
# Uses base DeducteeRecord — no additional fields needed beyond what's in base.
# Section codes: 193, 194, 194A, 194B, 194BB, 194C, 194D, 194DA, 194E, 194EE,
#                194F, 194G, 194H, 194I, 194IA, 194IB, 194IC, 194J, 194K,
#                194LA, 194LB, 194LBA, 194LBB, 194LBC, 194LC, 194LD, 194M,
#                194N, 194O, 194P, 194Q, 194R, 194S


# ---------------------------------------------------------------------------
# Form 27Q — TDS on payments to Non-Residents (Section 195 etc.)
# ---------------------------------------------------------------------------

class NonResidentDeducteeRecord(DeducteeRecord):
    """Form 27Q — TDS on payments to non-residents / foreign companies."""

    # Country and residency
    country_of_residence: str = ""
    tax_residency_certificate_no: Optional[str] = None
    trc_validity_from: Optional[date] = None
    trc_validity_to: Optional[date] = None

    # DTAA (Double Taxation Avoidance Agreement)
    dtaa_applicable: bool = False
    dtaa_article: Optional[str] = None           # Article of DTAA under which relief claimed
    dtaa_rate: Optional[Decimal] = None          # TDS rate under DTAA

    # Nature and details of remittance
    nature_of_remittance: str = ""               # Dividend / Interest / Royalty / FTS / Capital Gains / Other
    section: str = "195"                         # 195, 196A, 196B, 196C, 196D, 194E, 194LB, 194LC, 194LD

    # Remittance details
    remittance_currency: str = "INR"
    remittance_amount_foreign_currency: Decimal = Decimal("0")
    forex_rate: Decimal = Decimal("1")           # INR per foreign currency unit
    gross_amount_before_tds: Decimal = Decimal("0")
    tds_rate_applied: Optional[Decimal] = None   # Actual rate applied (may differ from standard if DTAA)

    # RBI / regulatory
    rbi_approval_no: Optional[str] = None
    form_15ca_ack_no: Optional[str] = None       # Form 15CA acknowledgement number
    form_15cb_cert_no: Optional[str] = None      # CA certificate number u/s 195(6)

    # Remittee contact
    email_of_remittee: Optional[str] = None
    contact_of_remittee: Optional[str] = None
    address_of_remittee: Optional[str] = None


# ---------------------------------------------------------------------------
# Form 27EQ — Tax Collected at Source (TCS, Section 206C)
# ---------------------------------------------------------------------------

class TCSRecord(BaseModel):
    """Form 27EQ — TCS record per buyer/licensee."""

    serial_no: int = Field(ge=1)
    buyer_pan: str = Field(description="10-char PAN of buyer / licensee / lessee")
    buyer_name: str
    buyer_type: str = "O"           # O=Other than company, C=Company

    # Section 206C sub-section
    section_206c: str = ""          # a=alcohol, b=timber/forest, c=scrap, d=minerals,
                                    # e=parking lot/toll, f=quarrying, g=TCS on sales >₹50L,
                                    # h=overseas remittance, i=foreign travel package,
                                    # j=overseas education, k=other goods

    nature_of_goods_or_services: str = ""

    # Amounts
    amount_collected: Decimal = Decimal("0")     # Sale / receipt amount
    tcs_rate: Decimal = Decimal("0")
    tcs_collected: Decimal = Decimal("0")
    surcharge: Decimal = Decimal("0")
    education_cess: Decimal = Decimal("0")
    total_tcs: Decimal = Decimal("0")

    # Date
    date_of_collection: Optional[date] = None

    # Lower TCS
    lower_tcs_reason: LowerDeductionReason = LowerDeductionReason.NONE
    certificate_no: Optional[str] = None
    certificate_date: Optional[date] = None
    last_pan_used: Optional[str] = None

    # 206CCA — higher TCS for non-filers
    higher_tcs_applicable: bool = False          # True if buyer didn't file ITR for 2 prior years

    @field_validator("buyer_pan")
    @classmethod
    def validate_pan(cls, v: str) -> str:
        v = v.strip().upper()
        if len(v) != 10:
            raise ValueError(f"PAN must be 10 characters, got: {v!r}")
        return v

    def date_ddmmyyyy(self, d: Optional[date]) -> str:
        return d.strftime("%d%m%Y") if d else ""

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Form 26QB — TDS on purchase of immovable property (Section 194IA)
# ---------------------------------------------------------------------------

class PropertyRecord(BaseModel):
    """Form 26QB — TDS on immovable property purchase (Section 194IA, rate 1%)."""

    serial_no: int = Field(ge=1)

    # Buyer (up to 2 buyers)
    buyer_pan_1: str
    buyer_name_1: str
    buyer_pan_2: Optional[str] = None
    buyer_name_2: Optional[str] = None

    # Seller (up to 2 sellers)
    seller_pan_1: str
    seller_name_1: str
    seller_pan_2: Optional[str] = None
    seller_name_2: Optional[str] = None

    # Property
    property_address: str = ""
    property_city: str = ""
    property_state: str = ""
    property_pincode: str = ""
    property_type: PropertyType = PropertyType.RESIDENTIAL

    # Transaction
    total_value_of_property: Decimal = Decimal("0")
    amount_paid_this_installment: Decimal = Decimal("0")
    date_of_agreement: Optional[date] = None
    date_of_payment: Optional[date] = None
    mode_of_payment: str = ""      # Cash / Cheque / DD / RTGS / NEFT / UPI / Others

    # TDS (Section 194IA — 1% of consideration)
    tds_rate: Decimal = Decimal("0.01")
    tds_deducted: Decimal = Decimal("0")
    surcharge: Decimal = Decimal("0")
    education_cess: Decimal = Decimal("0")
    total_tax: Decimal = Decimal("0")
    date_of_deduction: Optional[date] = None

    @field_validator("buyer_pan_1", "seller_pan_1")
    @classmethod
    def validate_pan(cls, v: str) -> str:
        v = v.strip().upper()
        if len(v) != 10:
            raise ValueError(f"PAN must be 10 characters, got: {v!r}")
        return v

    def date_ddmmyyyy(self, d: Optional[date]) -> str:
        return d.strftime("%d%m%Y") if d else ""

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Form 26QC — TDS on rent by Individual/HUF (Section 194IB)
# ---------------------------------------------------------------------------

class RentRecord(BaseModel):
    """Form 26QC — TDS on rent where tenant is Individual/HUF (Section 194IB, rate 5%)."""

    serial_no: int = Field(ge=1)

    # Tenant (deductor for this form)
    tenant_pan: str
    tenant_name: str

    # Landlord (deductee)
    landlord_pan: str
    landlord_name: str
    landlord_address: str = ""
    landlord_email: Optional[str] = None
    landlord_mobile: Optional[str] = None

    # Property
    property_address: str = ""
    property_city: str = ""
    property_state: str = ""
    property_pincode: str = ""
    property_type: PropertyType = PropertyType.RESIDENTIAL

    # Rent details
    from_date: Optional[date] = None             # Rent period start
    to_date: Optional[date] = None               # Rent period end (usually last month of FY)
    monthly_rent: Decimal = Decimal("0")
    total_rent_paid: Decimal = Decimal("0")      # For the period
    last_month_rent: Decimal = Decimal("0")      # TDS is deducted on last month's rent

    # TDS (Section 194IB — 5%; deducted once at end of FY or on vacating)
    tds_rate: Decimal = Decimal("0.05")
    tds_deducted: Decimal = Decimal("0")
    date_of_deduction: Optional[date] = None
    date_of_deposit: Optional[date] = None
    surcharge: Decimal = Decimal("0")
    education_cess: Decimal = Decimal("0")
    total_tax: Decimal = Decimal("0")

    @field_validator("tenant_pan", "landlord_pan")
    @classmethod
    def validate_pan(cls, v: str) -> str:
        v = v.strip().upper()
        if len(v) != 10:
            raise ValueError(f"PAN must be 10 characters, got: {v!r}")
        return v

    def date_ddmmyyyy(self, d: Optional[date]) -> str:
        return d.strftime("%d%m%Y") if d else ""

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Form 26QD — TDS on e-commerce payments (Section 194O)
# ---------------------------------------------------------------------------

class ECommerceRecord(BaseModel):
    """Form 26QD — TDS on payments by e-commerce operators to participants (Section 194O, rate 1%)."""

    serial_no: int = Field(ge=1)
    participant_pan: str
    participant_name: str
    participant_type: str = "O"      # O=Individual/HUF, C=Other

    nature_of_services_goods: str = ""
    gross_amount: Decimal = Decimal("0")    # Total sales / services facilitated
    tds_rate: Decimal = Decimal("0.01")     # 1% u/s 194O
    tds_deducted: Decimal = Decimal("0")
    surcharge: Decimal = Decimal("0")
    education_cess: Decimal = Decimal("0")
    total_tax: Decimal = Decimal("0")

    date_of_credit_or_payment: Optional[date] = None

    lower_deduction_reason: LowerDeductionReason = LowerDeductionReason.NONE
    certificate_no: Optional[str] = None
    certificate_date: Optional[date] = None

    @field_validator("participant_pan")
    @classmethod
    def validate_pan(cls, v: str) -> str:
        v = v.strip().upper()
        if len(v) != 10:
            raise ValueError(f"PAN must be 10 characters, got: {v!r}")
        return v

    def date_ddmmyyyy(self, d: Optional[date]) -> str:
        return d.strftime("%d%m%Y") if d else ""

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Form 26QE — TDS on Virtual Digital Assets (Section 194S)
# ---------------------------------------------------------------------------

class VDARecord(BaseModel):
    """Form 26QE — TDS on transfer of Virtual Digital Assets (crypto/NFT) u/s 194S, rate 1%."""

    serial_no: int = Field(ge=1)
    buyer_pan: str
    buyer_name: str
    buyer_type: str = "O"           # O=Other, C=Specified person (exchange)

    # VDA details
    nature_of_vda: str = ""         # Cryptocurrency / NFT / Other VDA
    vda_description: str = ""       # e.g. Bitcoin, Ethereum, NFT name
    date_of_transfer: Optional[date] = None

    # Amounts
    consideration_amount: Decimal = Decimal("0")     # Sale consideration
    tds_rate: Decimal = Decimal("0.01")              # 1% u/s 194S
    tds_deducted: Decimal = Decimal("0")
    surcharge: Decimal = Decimal("0")
    education_cess: Decimal = Decimal("0")
    total_tax: Decimal = Decimal("0")

    # Exchange / broker details
    exchange_name: Optional[str] = None
    exchange_pan: Optional[str] = None

    lower_deduction_reason: LowerDeductionReason = LowerDeductionReason.NONE
    certificate_no: Optional[str] = None

    @field_validator("buyer_pan")
    @classmethod
    def validate_pan(cls, v: str) -> str:
        v = v.strip().upper()
        if len(v) != 10:
            raise ValueError(f"PAN must be 10 characters, got: {v!r}")
        return v

    def date_ddmmyyyy(self, d: Optional[date]) -> str:
        return d.strftime("%d%m%Y") if d else ""

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Form 24G — TDS/TCS Book Adjustment Statement (Government deductors)
# ---------------------------------------------------------------------------

class GovernmentRecord(BaseModel):
    """Form 24G — Monthly book adjustment statement for government deductors (no bank challan)."""

    serial_no: int = Field(ge=1)
    section: str = ""
    minor_head: str = ""            # 200=TDS payable by taxpayer, 400=TDS on regular assessment
    nature_of_payment: str = ""

    # Amounts
    amount_transferred: Decimal = Decimal("0")   # Gross amount on which TDS applies
    tds_tcs_amount: Decimal = Decimal("0")
    surcharge: Decimal = Decimal("0")
    education_cess: Decimal = Decimal("0")
    interest: Decimal = Decimal("0")
    penalty: Decimal = Decimal("0")
    total_amount: Decimal = Decimal("0")

    # Transfer details
    date_of_transfer: Optional[date] = None
    transfer_voucher_no: Optional[str] = None

    # DDO (Drawing and Disbursing Officer)
    ddo_pan: Optional[str] = None
    ddo_name: str = ""
    ddo_designation: str = ""

    # Government office codes
    ministry_code: str = ""          # Ministry/Department code as per NSDL
    pay_accounts_code: str = ""      # PAO code (Pay and Accounts Office)
    ddo_code: str = ""               # DDO code within PAO

    def date_ddmmyyyy(self, d: Optional[date]) -> str:
        return d.strftime("%d%m%Y") if d else ""

    class Config:
        from_attributes = True
