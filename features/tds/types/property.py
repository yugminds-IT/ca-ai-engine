"""Constants and helpers for TDS on immovable property (Form 26QB — Section 194IA) and related."""

from decimal import Decimal

# Form 26QB — Section 194IA (buyer deducts TDS)
FORM_TYPE_26QB = "26QB"
SECTION_194IA = "194IA"
TDS_RATE_194IA = Decimal("0.01")           # 1% on consideration ≥ ₹50 lakh
THRESHOLD_194IA = Decimal("5_000_000")     # ₹50 lakh — no TDS below this

# Form 26QC — Section 194IB (tenant deducts TDS on rent)
FORM_TYPE_26QC = "26QC"
SECTION_194IB = "194IB"
TDS_RATE_194IB = Decimal("0.05")           # 5% on last month's rent
THRESHOLD_194IB_MONTHLY = Decimal("50_000")  # ₹50,000/month — no TDS below this

# Section 194IC — TDS on Joint Development Agreement
SECTION_194IC = "194IC"
TDS_RATE_194IC = Decimal("0.10")           # 10%

# Section 194I — TDS on rent by company/firm (via Form 26Q, NOT 26QC)
SECTION_194I_LAND_BUILDING = "194I(a)"    # Plant/machinery: 2%
SECTION_194I_PLANT = "194I(b)"            # Land/building/furniture: 10%
TDS_RATE_194I_LAND_BUILDING = Decimal("0.10")
TDS_RATE_194I_PLANT = Decimal("0.02")
THRESHOLD_194I = Decimal("240_000")        # ₹2.4 lakh annual — no TDS below this

# Property types
PROPERTY_TYPES = {
    "R": "Residential",
    "C": "Commercial",
    "L": "Land / Plot",
    "I": "Industrial",
}

# Payment modes (Form 26QB)
PAYMENT_MODES = {
    "CH": "Cheque",
    "DD": "Demand Draft",
    "CA": "Cash",
    "NT": "NEFT / RTGS",
    "UP": "UPI",
    "OT": "Others",
}

HEALTH_EDUCATION_CESS_RATE = Decimal("0.04")


def compute_tds_194ia(consideration: Decimal) -> Decimal:
    if consideration < THRESHOLD_194IA:
        return Decimal("0")
    return (consideration * TDS_RATE_194IA).quantize(Decimal("1"))


def compute_tds_194ib(last_month_rent: Decimal) -> Decimal:
    """TDS deducted on last month's rent (or at time of vacating)."""
    if last_month_rent < THRESHOLD_194IB_MONTHLY:
        return Decimal("0")
    return (last_month_rent * TDS_RATE_194IB).quantize(Decimal("1"))


def compute_tds_194i(annual_rent: Decimal, is_plant_machinery: bool = False) -> Decimal:
    if annual_rent < THRESHOLD_194I:
        return Decimal("0")
    rate = TDS_RATE_194I_PLANT if is_plant_machinery else TDS_RATE_194I_LAND_BUILDING
    return (annual_rent * rate).quantize(Decimal("1"))
