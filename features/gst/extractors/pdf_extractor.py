"""Convert PDF pages to PNG bytes using PyMuPDF at 200 DPI."""

from pathlib import Path

import fitz  # PyMuPDF
from loguru import logger


class PDFExtractor:
    def __init__(self, dpi: int = 200):
        self._dpi = dpi

    def to_pages(self, file_path: str | Path) -> list[bytes]:
        """Return a list of PNG bytes, one per page."""
        file_path = Path(file_path)
        doc = fitz.open(str(file_path))
        pages: list[bytes] = []
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=self._dpi)
            pages.append(pix.tobytes("png"))
            logger.debug(f"Rendered page {i + 1}/{len(doc)} of {file_path.name}")
        doc.close()
        return pages
