"""Constants and helpers for Tax Collected at Source (Form 27EQ, Section 206C)."""

from decimal import Decimal

FORM_TYPE = "27EQ"
SECTION = "206C"

# Sub-sections of 206C and their descriptions
SUBSECTIONS: dict[str, str] = {
    "206C(1)(a)":  "Alcoholic liquor for human consumption",
    "206C(1)(b)":  "Tendu leaves",
    "206C(1)(c)":  "Timber obtained under forest lease",
    "206C(1)(d)":  "Timber obtained by any other mode",
    "206C(1)(e)":  "Any other forest produce (not timber/tendu)",
    "206C(1)(f)":  "Scrap",
    "206C(1)(g)":  "Minerals — coal, lignite, iron ore",
    "206C(1C)":    "Parking lot / toll plaza / mining and quarrying",
    "206C(1F)":    "Motor vehicle sale > ₹10 lakh",
    "206C(1G)(a)": "Overseas remittance (LRS) — other than education/medical",
    "206C(1G)(b)": "Overseas education remittance (loan-funded) under LRS",
    "206C(1G)(c)": "Overseas education remittance (own funds) under LRS",
    "206C(1G)(d)": "Overseas medical remittance under LRS",
    "206C(1H)":    "Sale of goods > ₹50 lakh (seller's turnover > ₹10 Cr)",
}

# TCS rates (% of sale consideration / remittance amount)
TCS_RATES: dict[str, Decimal] = {
    "206C(1)(a)":  Decimal("0.01"),   # 1%
    "206C(1)(b)":  Decimal("0.05"),   # 5%
    "206C(1)(c)":  Decimal("0.025"),  # 2.5%
    "206C(1)(d)":  Decimal("0.025"),  # 2.5%
    "206C(1)(e)":  Decimal("0.025"),  # 2.5%
    "206C(1)(f)":  Decimal("0.01"),   # 1%
    "206C(1)(g)":  Decimal("0.01"),   # 1%
    "206C(1C)":    Decimal("0.02"),   # 2%
    "206C(1F)":    Decimal("0.01"),   # 1%
    "206C(1G)(a)": Decimal("0.20"),   # 20% (LRS others) — FY 2024-25 onward
    "206C(1G)(b)": Decimal("0.005"),  # 0.5% (education via loan)
    "206C(1G)(c)": Decimal("0.05"),   # 5% (education own funds)
    "206C(1G)(d)": Decimal("0.05"),   # 5% (medical)
    "206C(1H)":    Decimal("0.001"),  # 0.1%
}

# 206CCA — higher TCS for non-filers (2× normal rate or 5%, whichever is higher)
HIGHER_TCS_MULTIPLIER = Decimal("2")
HIGHER_TCS_FLOOR = Decimal("0.05")

HEALTH_EDUCATION_CESS_RATE = Decimal("0.04")


def compute_tcs(amount: Decimal, subsection: str) -> Decimal:
    rate = TCS_RATES.get(subsection, Decimal("0.01"))
    return (amount * rate).quantize(Decimal("1"))


def compute_higher_tcs(amount: Decimal, subsection: str) -> Decimal:
    normal_rate = TCS_RATES.get(subsection, Decimal("0.01"))
    higher_rate = max(normal_rate * HIGHER_TCS_MULTIPLIER, HIGHER_TCS_FLOOR)
    return (amount * higher_rate).quantize(Decimal("1"))
