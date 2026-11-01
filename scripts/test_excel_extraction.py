"""
Test Excel extraction.

Usage:
    python scripts/test_excel_extraction.py <excel_path> [output_json_path]
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from features.tds.extractors.excel_extractor import ExcelExtractor


def main():
    excel_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "tds-doc/Salary Breakup details- DEUS IT SOLUTIONS.xlsx"
    )
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(
        f"output/{excel_path.stem}_extracted.json"
    )

    if not excel_path.exists():
        print(f"ERROR: File not found: {excel_path}", file=sys.stderr)
        sys.exit(1)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Extracting: {excel_path}")
    extractor = ExcelExtractor()
    result = extractor.extract_to_json(excel_path, tds_type="salary")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    print(f"Saved to:   {out_path}")
    print(f"Records:    {len(result)}")
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
