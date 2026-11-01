"""Constants and helpers for Rent TDS (Form 26Q, Section 194I / 194IB)."""

from decimal import Decimal

FORM_TYPE = "26Q"
SECTION_LAND_BUILDING = "194I"     # Plant, machinery, land, building, furniture
SECTION_INDIVIDUAL_HUF = "194IB"   # Individual/HUF monthly rent > 50k

TDS_RATE_LAND_BUILDING = Decimal("0.10")     # 10%
TDS_RATE_PLANT_MACHINERY = Decimal("0.02")   # 2%
TDS_RATE_INDIVIDUAL_HUF = Decimal("0.05")    # 5%

THRESHOLD_194I = Decimal("240000")   # Annual limit for 194I
THRESHOLD_194IB = Decimal("50000")   # Monthly limit for 194IB


def compute_tds_194i(
    amount: Decimal,
    is_plant_machinery: bool = False,
) -> Decimal:
    rate = TDS_RATE_PLANT_MACHINERY if is_plant_machinery else TDS_RATE_LAND_BUILDING
    return (amount * rate).quantize(Decimal("1"))


def compute_tds_194ib(monthly_rent: Decimal) -> Decimal:
    return (monthly_rent * TDS_RATE_INDIVIDUAL_HUF).quantize(Decimal("1"))
