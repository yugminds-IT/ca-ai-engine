"""
Export GST invoice extraction results to a color-coded Excel workbook.

Row fill:
  RED   (FFE6E6) — error   (invalid GSTIN, tax mismatch, missing required field)
  AMBER (FFF3CD) — review  (warnings: missing party name, zero total)
  WHITE (FFFFFF) — ok
"""

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from features.gst.schemas.invoice import ExtractionResult, ValidationStatus

_FILL_ERROR  = PatternFill("solid", fgColor="FFE6E6")
_FILL_REVIEW = PatternFill("solid", fgColor="FFF3CD")
_FILL_OK     = PatternFill("solid", fgColor="FFFFFF")
_FILL_HEADER = PatternFill("solid", fgColor="1F4E79")
_FONT_HEADER = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
_FONT_BODY   = Font(name="Calibri", size=10)

_COLUMNS = [
    ("Source File",       18),
    ("Page",               6),
    ("GSTIN",             18),
    ("Invoice No.",       16),
    ("Invoice Date",      14),
    ("Party Name",        28),
    ("Taxable Value",     14),
    ("CGST",              10),
    ("SGST",              10),
    ("IGST",              10),
    ("Total",             12),
    ("Status",            10),
    ("Errors / Warnings", 44),
]

_ROW_FILL = {
    ValidationStatus.error:  _FILL_ERROR,
    ValidationStatus.review: _FILL_REVIEW,
    ValidationStatus.ok:     _FILL_OK,
}


class ExcelExporter:
    def export(self, result: ExtractionResult, output_path: str | Path) -> Path:
        """Write extraction result to a color-coded .xlsx file and return the path."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        wb = Workbook()
        ws = wb.active
        ws.title = "GST Invoices"

        # Header row
        for col, (header, width) in enumerate(_COLUMNS, start=1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = _FONT_HEADER
            cell.fill = _FILL_HEADER
            cell.alignment = Alignment(horizontal="center", vertical="center")
            ws.column_dimensions[get_column_letter(col)].width = width
        ws.row_dimensions[1].height = 22

        # Data rows
        for row, record in enumerate(result.records, start=2):
            inv = record.invoice
            val = record.validation
            issues = "; ".join(val.errors + val.warnings)
            row_data = [
                inv.source_file,
                inv.page_no,
                inv.gstin,
                inv.invoice_no,
                inv.invoice_date,
                inv.party_name,
                float(inv.taxable_value),
                float(inv.cgst),
                float(inv.sgst),
                float(inv.igst),
                float(inv.total),
                val.status.value.upper(),
                issues,
            ]
            fill = _ROW_FILL[val.status]
            for col, value in enumerate(row_data, start=1):
                cell = ws.cell(row=row, column=col, value=value)
                cell.font = _FONT_BODY
                cell.fill = fill
                cell.alignment = Alignment(vertical="center")

        # Summary sheet
        ws2 = wb.create_sheet("Summary")
        ws2.append(["Metric", "Value"])
        ws2.append(["Source File",     result.source_file])
        ws2.append(["Total Pages",     result.total_pages])
        ws2.append(["Total Invoices",  result.total_invoices])
        ws2.append(["OK",              result.ok_count])
        ws2.append(["Review",          result.review_count])
        ws2.append(["Error",           result.error_count])

        wb.save(str(output_path))
        return output_path
