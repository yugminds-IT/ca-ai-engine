"""
Run challan extraction (PyMuPDF fitz + dynamic key-value parsing) and save output.

Usage:
    python scripts/test_challan_extraction.py <pdf_path> [output_json_path]
"""

import json
import sys
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from features.tds.extractors.challan_extractor import ChallanExtractor


def main() -> None:
    pdf_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "tds-doc/26052900117523ICIC_ChallanReceipt.pdf"
    )
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(
        f"output/{pdf_path.stem}_extracted.json"
    )

    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Extracting: {pdf_path}")
    extractor = ChallanExtractor()
    result = extractor.extract_to_json(pdf_path)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    print(f"Saved to:   {out_path}")
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
