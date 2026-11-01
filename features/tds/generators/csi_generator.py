"""
CSI (Challan Status Inquiry) file generator — OLTAS format.

The .csi file is the standard Challan Status Inquiry file used in India's
TDS workflow:
  • OLTAS (Online Tax Accounting System) provides this file after you deposit
    tax at a bank branch or via net banking.
  • The RPU (Return Preparation Utility) imports this file to pre-verify
    challan details before return submission.
  • CAs generate / share this file with clients to confirm deposit status.

File format (comma-separated, one challan per line):
  Col 1  — BSR Code of bank branch (7 digits)
  Col 2  — Challan Tender Date (DDMMYYYY)
  Col 3  — Challan Serial Number (5 digits, zero-padded)
  Col 4  — Total Amount deposited (in Rupees, NOT paise)
  Col 5  — Major Head Code (0020 = Companies, 0021 = Others)
  Col 6  — TAN of deductor
  Col 7  — Name of deductor
  Col 8  — Minor Head Code (200 = TDS payable by taxpayer)
  Col 9  — Nature of Payment (section code e.g. 92B, 194J, 194I)
  Col 10 — Status (F = Final, P = Provisional)

Example line for the ICICI challan:
  6390009,29052026,12188,26923,0021,HYDD06852G,DEUS IT SOLUTIONS PRIVATE LIMITED,200,92B,F
"""

from decimal import Decimal
from typing import Optional

from features.tds.schemas.challan import ChallanData
from features.tds.schemas.return_file import TDSReturn


class CSIGenerator:
    """Generate OLTAS-format .csi challan status inquiry files."""

    STATUS_FINAL = "F"
    STATUS_PROVISIONAL = "P"

    # ------------------------------------------------------------------ public

    def generate_from_challan(
        self,
        challan: ChallanData,
        status: str = "F",
    ) -> str:
        """Generate a single-challan .csi file string."""
        return self._challan_line(challan, status)

    def generate_from_return(
        self,
        return_data: TDSReturn,
        status: str = "F",
    ) -> str:
        """Generate a .csi file with one line per challan in the return."""
        lines = [
            self._challan_line(bundle.challan, status)
            for bundle in return_data.challans
        ]
        return "\r\n".join(lines) + "\r\n"

    def generate_from_challans(
        self,
        challans: list[ChallanData],
        status: str = "F",
    ) -> str:
        """Generate a .csi file from a plain list of ChallanData objects."""
        lines = [self._challan_line(c, status) for c in challans]
        return "\r\n".join(lines) + "\r\n"

    # ----------------------------------------------------------------- private

    def _challan_line(self, c: ChallanData, status: str) -> str:
        fields = [
            c.bsr_code,                             # Col 1 — BSR Code
            c.challan_deposit_ddmmyyyy(),            # Col 2 — Tender date DDMMYYYY
            str(c.challan_no).zfill(5),             # Col 3 — Challan serial (zero-padded)
            str(int(c.total_amount)),               # Col 4 — Amount in Rupees
            c.major_head,                           # Col 5 — Major head (0020/0021)
            c.tan,                                  # Col 6 — TAN
            c.deductor_name,                        # Col 7 — Deductor name
            c.minor_head,                           # Col 8 — Minor head (200)
            c.nature_of_payment,                    # Col 9 — Section / nature of payment
            status,                                 # Col 10 — F=Final, P=Provisional
        ]
        return ",".join(fields)
