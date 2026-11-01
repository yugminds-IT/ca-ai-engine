"""Constants and helpers for Form 24G — TDS/TCS Book Adjustment Statement (Government deductors)."""

from decimal import Decimal

FORM_TYPE = "24G"

# Government deductor types
GOVERNMENT_TYPES = {
    "C": "Central Government",
    "S": "State Government",
    "L": "Local Authority",
}

# Minor head codes for government payments
MINOR_HEAD = {
    "200": "TDS / TCS payable by taxpayer",
    "400": "TDS / TCS on regular assessment",
}

# Sections commonly used by government deductors
GOVT_SECTIONS = {
    "92A":  "Salary (same employer)",
    "92B":  "Salary (previous employer)",
    "193":  "Interest on securities",
    "194":  "Dividend",
    "194A": "Interest other than securities",
    "194B": "Winnings from lottery / crossword puzzle",
    "194C": "Contractor / sub-contractor",
    "194G": "Commission on lottery tickets",
    "194H": "Commission / brokerage",
    "194I": "Rent",
    "194J": "Professional / technical fees",
    "194LA": "Compensation on acquisition of immovable property",
    "206C": "TCS — various goods",
}

# PAO (Pay and Accounts Office) filing frequency
FILING_FREQUENCY = "Monthly"   # Form 24G is filed monthly, not quarterly

HEALTH_EDUCATION_CESS_RATE = Decimal("0.04")


def validate_ain(ain: str) -> bool:
    """AIN is a 7-digit numeric code assigned by ITD to government account offices."""
    return ain.isdigit() and len(ain) == 7
