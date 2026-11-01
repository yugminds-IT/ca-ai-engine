"""Constants and helpers for Salary TDS (Form 24Q, Section 192 / 92B)."""

from decimal import Decimal

FORM_TYPE = "24Q"
SECTION_SAME_EMPLOYER = "92A"
SECTION_PREVIOUS_EMPLOYER = "92B"

# Tax slab rates for FY 2025-26 under new regime (default)
NEW_REGIME_SLABS = [
    (300_000, Decimal("0")),
    (700_000, Decimal("0.05")),
    (1_000_000, Decimal("0.10")),
    (1_200_000, Decimal("0.15")),
    (1_500_000, Decimal("0.20")),
    (float("inf"), Decimal("0.30")),
]

STANDARD_DEDUCTION = Decimal("75000")
HEALTH_EDUCATION_CESS_RATE = Decimal("0.04")


def compute_tax_new_regime(taxable_income: Decimal) -> Decimal:
    """Compute income tax under new regime for FY 2025-26."""
    tax = Decimal("0")
    prev_slab = Decimal("0")
    for slab, rate in NEW_REGIME_SLABS:
        slab_d = Decimal(str(slab))
        if taxable_income <= slab_d:
            tax += (taxable_income - prev_slab) * rate
            break
        tax += (slab_d - prev_slab) * rate
        prev_slab = slab_d
    return tax.quantize(Decimal("1"))


def compute_cess(tax: Decimal) -> Decimal:
    return (tax * HEALTH_EDUCATION_CESS_RATE).quantize(Decimal("1"))


def quarterly_tds(annual_tax: Decimal, quarter: int = 4) -> Decimal:
    """Spread annual TDS across remaining quarters."""
    return (annual_tax / Decimal(str(5 - quarter))).quantize(Decimal("1"))
