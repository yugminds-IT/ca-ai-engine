"""GST invoice validators: GSTIN checksum and tax math."""

from decimal import Decimal

from features.gst.schemas.invoice import InvoiceData, ValidationResult, ValidationStatus

_CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_TAX_TOLERANCE = Decimal("1.00")


def _gstin_checksum_valid(gstin: str) -> bool:
    """Verify 15-char GSTIN via alternating-weight (1/2) checksum algorithm."""
    if len(gstin) != 15:
        return False
    gstin = gstin.upper()
    total = 0
    for i, ch in enumerate(gstin[:-1]):
        if ch not in _CHARSET:
            return False
        factor = 1 if i % 2 == 0 else 2
        product = _CHARSET.index(ch) * factor
        total += (product // 36) + (product % 36)
    check_idx = (36 - (total % 36)) % 36
    return gstin[-1] == _CHARSET[check_idx]


class GSTValidator:
    def validate(self, invoice: InvoiceData) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        gstin_valid = True
        tax_sum_valid = True

        # --- GSTIN ---
        if not invoice.gstin:
            errors.append("GSTIN missing")
            gstin_valid = False
        elif len(invoice.gstin) != 15:
            errors.append(f"GSTIN must be 15 characters, got {len(invoice.gstin)}: {invoice.gstin!r}")
            gstin_valid = False
        elif not _gstin_checksum_valid(invoice.gstin):
            errors.append(f"GSTIN checksum invalid: {invoice.gstin}")
            gstin_valid = False

        # --- Required text fields ---
        if not invoice.invoice_no:
            errors.append("Invoice number missing")
        if not invoice.invoice_date:
            errors.append("Invoice date missing")
        if not invoice.party_name:
            warnings.append("Party name missing")

        # --- Tax math: taxable_value + CGST + SGST + IGST ≈ total ---
        if invoice.total > Decimal("0"):
            computed = invoice.taxable_value + invoice.cgst + invoice.sgst + invoice.igst
            diff = abs(computed - invoice.total)
            if diff > _TAX_TOLERANCE:
                errors.append(
                    f"Tax sum mismatch: {invoice.taxable_value} + {invoice.cgst} + "
                    f"{invoice.sgst} + {invoice.igst} = {computed:.2f}, "
                    f"expected {invoice.total:.2f} (diff ₹{diff:.2f})"
                )
                tax_sum_valid = False
        else:
            warnings.append("Invoice total is zero — verify amounts")

        status = (
            ValidationStatus.error if errors
            else ValidationStatus.review if warnings
            else ValidationStatus.ok
        )

        return ValidationResult(
            status=status,
            errors=errors,
            warnings=warnings,
            gstin_valid=gstin_valid,
            tax_sum_valid=tax_sum_valid,
        )
