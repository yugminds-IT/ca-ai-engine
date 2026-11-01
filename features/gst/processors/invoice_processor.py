"""Batch process a GST invoice file: extract → validate → return ExtractionResult."""

from pathlib import Path

import fitz  # PyMuPDF
from loguru import logger

from features.gst.extractors.invoice_extractor import InvoiceExtractor
from features.gst.schemas.invoice import ExtractionResult, InvoiceRecord
from features.gst.validators.gst_validator import GSTValidator


class InvoiceProcessor:
    def __init__(self) -> None:
        self._extractor = InvoiceExtractor()
        self._validator = GSTValidator()

    def process(self, file_path: str | Path) -> ExtractionResult:
        """Extract and validate all invoices in a file."""
        file_path = Path(file_path)

        total_pages = 1
        if file_path.suffix.lower() == ".pdf":
            doc = fitz.open(str(file_path))
            total_pages = len(doc)
            doc.close()

        logger.info(f"Processing {file_path.name} ({total_pages} page(s))")
        invoices = self._extractor.extract(file_path)

        records: list[InvoiceRecord] = [
            InvoiceRecord(invoice=inv, validation=self._validator.validate(inv))
            for inv in invoices
        ]

        result = ExtractionResult(
            source_file=file_path.name,
            total_pages=total_pages,
            total_invoices=len(records),
            records=records,
        )
        logger.info(
            f"{file_path.name}: {result.ok_count} ok, "
            f"{result.review_count} review, {result.error_count} error"
        )
        return result

    def process_to_json(self, file_path: str | Path) -> dict:
        """Process file and return JSON-serialisable dict."""
        return self.process(file_path).model_dump(mode="json")
