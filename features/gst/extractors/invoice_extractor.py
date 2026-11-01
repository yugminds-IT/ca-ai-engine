"""
Orchestrator: accepts a PDF or image file and returns a list of InvoiceData.

PDF   → rendered to per-page PNGs via PDFExtractor (PyMuPDF, 150 DPI)
         → each page passed to ImageExtractor (SmolVLM via HuggingFace).
Image → passed directly to ImageExtractor.
"""

from pathlib import Path

from loguru import logger

from features.gst.extractors.image_extractor import ImageExtractor
from features.gst.extractors.pdf_extractor import PDFExtractor
from features.gst.schemas.invoice import InvoiceData

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


class InvoiceExtractor:
    def __init__(self) -> None:
        self._pdf = PDFExtractor(dpi=150)
        self._ocr = ImageExtractor()

    def extract(self, file_path: str | Path) -> list[InvoiceData]:
        """Extract GST invoice data from a PDF or image file."""
        file_path = Path(file_path)
        ext = file_path.suffix.lower()

        if ext == ".pdf":
            return self._extract_pdf(file_path)
        if ext in _IMAGE_EXTS:
            return self._extract_image(file_path)
        raise ValueError(f"Unsupported file type: {ext!r}. Expected .pdf or image.")

    # ------------------------------------------------------------------

    def _extract_pdf(self, file_path: Path) -> list[InvoiceData]:
        import time
        pages = self._pdf.to_pages(file_path)
        total = len(pages)
        logger.info(f"Extracting {total} page(s) from {file_path.name}")
        results: list[InvoiceData] = []
        for i, page_bytes in enumerate(pages, start=1):
            logger.info(f"  OCR page {i}/{total} …")
            t0 = time.perf_counter()
            try:
                fields = self._ocr.extract(page_bytes)
                elapsed = time.perf_counter() - t0
                logger.info(f"  page {i}/{total} done in {elapsed:.1f}s — invoice: {fields.get('invoice_no') or '—'}")
                results.append(InvoiceData(**fields, source_file=file_path.name, page_no=i))
            except Exception as exc:
                logger.error(f"  page {i}/{total} failed: {exc}")
                results.append(InvoiceData(source_file=file_path.name, page_no=i))
        return results

    def _extract_image(self, file_path: Path) -> list[InvoiceData]:
        try:
            fields = self._ocr.extract(file_path.read_bytes())
            return [InvoiceData(**fields, source_file=file_path.name, page_no=1)]
        except Exception as exc:
            logger.error(f"OCR failed for {file_path.name}: {exc}")
            return [InvoiceData(source_file=file_path.name, page_no=1)]
