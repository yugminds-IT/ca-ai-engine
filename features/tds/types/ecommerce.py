"""Constants and helpers for TDS on e-commerce and VDA payments (Forms 26QD, 26QE)."""

from decimal import Decimal

# ---------------------------------------------------------------------------
# Form 26QD — Section 194O (e-commerce operator TDS)
# ---------------------------------------------------------------------------

FORM_TYPE_26QD = "26QD"
SECTION_194O = "194O"
TDS_RATE_194O = Decimal("0.01")            # 1% on gross amount
THRESHOLD_194O = Decimal("500_000")        # ₹5 lakh/year — no TDS below this for individuals

# Section 194Q — TDS on purchase of goods by buyer (turnover > ₹10 Cr)
SECTION_194Q = "194Q"
TDS_RATE_194Q = Decimal("0.001")           # 0.1% on purchase amount
THRESHOLD_194Q = Decimal("5_000_000")      # ₹50 lakh per seller per year

# Section 194R — TDS on perquisites / benefits
SECTION_194R = "194R"
TDS_RATE_194R = Decimal("0.10")            # 10%
THRESHOLD_194R = Decimal("20_000")         # ₹20,000 per recipient per year

# ---------------------------------------------------------------------------
# Form 26QE — Section 194S (VDA / Crypto / NFT TDS)
# ---------------------------------------------------------------------------

FORM_TYPE_26QE = "26QE"
SECTION_194S = "194S"
TDS_RATE_194S = Decimal("0.01")            # 1% on consideration
THRESHOLD_194S_SPECIFIED = Decimal("50_000")   # ₹50,000/year for specified persons (exchanges)
THRESHOLD_194S_OTHERS = Decimal("10_000")      # ₹10,000/year for others

# Nature of VDA
VDA_TYPES = {
    "CRYPTO":     "Cryptocurrency (Bitcoin, Ethereum, etc.)",
    "NFT":        "Non-Fungible Token",
    "TOKEN":      "Other Virtual Digital Asset / Token",
    "METAVERSE":  "Metaverse asset",
    "OTHER":      "Other VDA",
}

HEALTH_EDUCATION_CESS_RATE = Decimal("0.04")


def compute_tds_194o(gross_amount: Decimal) -> Decimal:
    return (gross_amount * TDS_RATE_194O).quantize(Decimal("1"))


def compute_tds_194s(consideration: Decimal) -> Decimal:
    return (consideration * TDS_RATE_194S).quantize(Decimal("1"))


def compute_tds_194q(purchase_amount: Decimal) -> Decimal:
    return (purchase_amount * TDS_RATE_194Q).quantize(Decimal("1"))
