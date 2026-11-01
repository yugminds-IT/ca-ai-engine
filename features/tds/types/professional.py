"""Constants and helpers for Professional Income TDS (Form 26Q, Section 194J)."""

from decimal import Decimal

FORM_TYPE = "26Q"
SECTION = "194J"

TDS_RATE_PROFESSIONAL = Decimal("0.10")   # 10% — professional/technical services
TDS_RATE_TECHNICAL = Decimal("0.02")      # 2% — technical services (sub-section b)
TDS_RATE_DIRECTOR = Decimal("0.10")       # 10% — fees to director
THRESHOLD_LIMIT = Decimal("30000")        # No TDS below this per year


def compute_tds(amount: Decimal, rate: Decimal = TDS_RATE_PROFESSIONAL) -> Decimal:
    return (amount * rate).quantize(Decimal("1"))


def is_above_threshold(amount: Decimal) -> bool:
    return amount > THRESHOLD_LIMIT
