"""Constants and helpers for TDS on Non-Resident payments (Form 27Q)."""

from decimal import Decimal

FORM_TYPE = "27Q"

# Sections applicable to Form 27Q
SECTIONS = {
    "195":    "Other sums payable to non-residents",
    "196A":   "Income from units of offshore fund",
    "196B":   "Income from units (NRI)",
    "196C":   "Income from foreign currency bonds / GDR",
    "196D":   "Income of FIIs from securities",
    "194E":   "Payments to non-resident sportsmen / sports association",
    "194LB":  "Interest from infrastructure debt fund (non-resident)",
    "194LBA": "Income from business trust (non-resident unit holder)",
    "194LBB": "Income from investment fund (non-resident)",
    "194LBC": "Income in respect of investment in securitisation trust",
    "194LC":  "Interest on foreign borrowings by Indian company",
    "194LD":  "Interest on rupee-denominated bonds / govt securities (FII/QFI)",
}

# Nature of remittance codes (used in Form 15CA/15CB as well)
NATURE_OF_REMITTANCE = {
    "DIV":  "Dividend",
    "INT":  "Interest",
    "ROY":  "Royalty",
    "FTS":  "Fees for technical services",
    "CG":   "Capital gains",
    "SAL":  "Salary",
    "BUS":  "Business income",
    "OTH":  "Other income",
}

# Standard TDS rates (may be reduced by DTAA)
TDS_RATE_195_DEFAULT = Decimal("0.20")    # 20% + surcharge + cess (no DTAA)
TDS_RATE_194E = Decimal("0.20")           # 20%
TDS_RATE_196A = Decimal("0.20")           # 20%
TDS_RATE_196B = Decimal("0.10")           # 10%
TDS_RATE_196C = Decimal("0.10")           # 10%
TDS_RATE_196D = Decimal("0.20")           # 20%
TDS_RATE_194LC = Decimal("0.05")          # 5%
TDS_RATE_194LD = Decimal("0.05")          # 5%

# Surcharge rates on TDS (for non-residents)
SURCHARGE_RATES = {
    "individual": [
        (5_000_000, Decimal("0.10")),
        (10_000_000, Decimal("0.15")),
        (20_000_000, Decimal("0.25")),
        (float("inf"), Decimal("0.37")),
    ],
    "foreign_company": [
        (10_000_000, Decimal("0.02")),
        (float("inf"), Decimal("0.05")),
    ],
}

HEALTH_EDUCATION_CESS_RATE = Decimal("0.04")


def effective_tds_rate(base_rate: Decimal, surcharge_rate: Decimal) -> Decimal:
    """Gross-up TDS rate including surcharge and cess."""
    with_surcharge = base_rate * (1 + surcharge_rate)
    return (with_surcharge * (1 + HEALTH_EDUCATION_CESS_RATE)).quantize(Decimal("0.0001"))
