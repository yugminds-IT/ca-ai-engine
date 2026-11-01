"""
TDS API routes.

Two output formats:
  .csi  — OLTAS Challan Status Inquiry (comma-separated challan rows)
  .txt  — NSDL FVU return file (pipe-delimited BH/CD/DD/BT records)

Flow:
  1. POST /upload/challan     → extract PDF → ChallanData JSON
  2. POST /upload/excel       → extract Excel → [DeducteeRecord] JSON
  3. POST /prepare            → Annexure I + II preview (sync)
  4. POST /generate/csi       → queue CSI file task → task_id
  5. POST /generate/fvu       → queue FVU return file task → task_id
  6. GET  /status/{task_id}   → poll Celery
  7. GET  /download/{task_id} → stream the generated file
"""

import re
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Literal

from celery.result import AsyncResult
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from loguru import logger

from config.settings import get_settings
from features.tds.extractors.challan_extractor import ChallanExtractor
from features.tds.extractors.excel_extractor import ExcelExtractor
from features.tds.processors.form_24q import Form24QProcessor
from features.tds.processors.form_26q import Form26QProcessor
from features.tds.validators.tds_validator import TDSValidator
from features.tds.schemas.challan import ChallanData
from features.tds.schemas.deductee import DeducteeRecord
from workers.tasks.tds.generation_tasks import (
    generate_csi_file,
    generate_24q_fvu,
    generate_26q_fvu,
)

settings = get_settings()
router = APIRouter()
_challan_extractor = ChallanExtractor()
_excel_extractor = ExcelExtractor()
_validator = TDSValidator()

# ---------------------------------------------------------------------------
# Form registry — static metadata about TDS/TCS form types and sections
# ---------------------------------------------------------------------------

_FORM_REGISTRY = {
    # ── Salary ──────────────────────────────────────────────────────────────
    "24Q": {
        "label": "Form 24Q",
        "description": "TDS on Salary Payments to Resident Employees",
        "category": "Salary",
        "type": "TDS",
        "old_name": "24Q",
        "new_name": "138",
        "sections": [
            {"code": "92B",  "label": "Section 192B — Salary"},
            {"code": "192A", "label": "Section 192A — Premature EPF / PF Withdrawal"},
        ],
    },
    # ── Non-salary (Residents) ───────────────────────────────────────────────
    "26Q": {
        "label": "Form 26Q",
        "description": "TDS on Non-Salary Payments to Resident Parties",
        "category": "Non-Salary (Residents)",
        "type": "TDS",
        "old_name": "26Q",
        "new_name": "140",
        "sections": [
            {"code": "193",    "label": "Section 193 — Interest on Securities"},
            {"code": "194",    "label": "Section 194 — Dividend (Domestic companies)"},
            {"code": "194A",   "label": "Section 194A — Interest (other than securities)"},
            {"code": "194B",   "label": "Section 194B — Lottery / Crossword Puzzle Winnings"},
            {"code": "194BB",  "label": "Section 194BB — Horse Race Winnings"},
            {"code": "194C",   "label": "Section 194C — Contractors / Sub-contractors"},
            {"code": "194D",   "label": "Section 194D — Insurance Commission"},
            {"code": "194DA",  "label": "Section 194DA — Life Insurance Policy Maturity"},
            {"code": "194EE",  "label": "Section 194EE — NSS Deposits"},
            {"code": "194F",   "label": "Section 194F — Repurchase of Units by MF / UTI"},
            {"code": "194G",   "label": "Section 194G — Commission / Prize on Lottery Tickets"},
            {"code": "194H",   "label": "Section 194H — Commission / Brokerage"},
            {"code": "194I(a)", "label": "Section 194I(a) — Rent on Plant & Machinery"},
            {"code": "194I(b)", "label": "Section 194I(b) — Rent on Land / Building / Furniture"},
            {"code": "194IA",  "label": "Section 194IA — TDS on Immovable Property Purchase"},
            {"code": "194IB",  "label": "Section 194IB — Rent by Individual / HUF (>₹50k/month)"},
            {"code": "194IC",  "label": "Section 194IC — Payment under Joint Development Agreement"},
            {"code": "194J(a)", "label": "Section 194J(a) — Technical Services / Call Centre"},
            {"code": "194J(b)", "label": "Section 194J(b) — Professional / Royalty / Non-compete"},
            {"code": "194K",   "label": "Section 194K — Income from Mutual Fund Units"},
            {"code": "194LA",  "label": "Section 194LA — Compensation (Land Acquisition)"},
            {"code": "194LBA", "label": "Section 194LBA — Business Trust Distributions"},
            {"code": "194LBB", "label": "Section 194LBB — Investments in AIF"},
            {"code": "194LBC", "label": "Section 194LBC — Securitisation Trust Income"},
            {"code": "194M",   "label": "Section 194M — Payment by Individuals / HUF (>₹50L)"},
            {"code": "194N",   "label": "Section 194N — Cash Withdrawals from Bank"},
            {"code": "194O",   "label": "Section 194O — E-commerce Operator Payments"},
            {"code": "194P",   "label": "Section 194P — TDS on Senior Citizen Pension"},
            {"code": "194Q",   "label": "Section 194Q — Purchase of Goods (>₹50L)"},
            {"code": "194R",   "label": "Section 194R — Benefits / Perquisites in Business"},
            {"code": "194S",   "label": "Section 194S — TDS on Transfer of Virtual Digital Assets"},
            {"code": "194T",   "label": "Section 194T — Payments to Partners of a Firm"},
        ],
    },
    # ── Non-residents ────────────────────────────────────────────────────────
    "27Q": {
        "label": "Form 27Q",
        "description": "TDS on Non-Salary Payments to Non-Residents / Foreign Companies",
        "category": "Non-Residents",
        "type": "TDS",
        "old_name": "27Q",
        "new_name": "144",
        "sections": [
            {"code": "194E",   "label": "Section 194E — Non-Resident Sportsmen / Entertainers"},
            {"code": "194LB",  "label": "Section 194LB — Interest from Infrastructure Debt Fund"},
            {"code": "194LC",  "label": "Section 194LC — Interest on Foreign Currency Borrowing"},
            {"code": "194LD",  "label": "Section 194LD — Interest on Bonds (FIIs/QFIs)"},
            {"code": "195",    "label": "Section 195 — Other Sums to Non-Residents"},
            {"code": "196A",   "label": "Section 196A — Income from Units (Non-Resident)"},
            {"code": "196B",   "label": "Section 196B — Income from Offshore Fund"},
            {"code": "196C",   "label": "Section 196C — Income from Foreign Currency Bonds"},
            {"code": "196D",   "label": "Section 196D — Income of FIIs from Securities"},
        ],
    },
    # ── TCS ──────────────────────────────────────────────────────────────────
    "27EQ": {
        "label": "Form 27EQ",
        "description": "TCS — Tax Collected at Source",
        "category": "TCS",
        "type": "TCS",
        "old_name": "27EQ",
        "new_name": "143",
        "sections": [
            {"code": "206C(1)",   "label": "206C(1) — TCS on Alcoholic Liquor / Timber / Forest Produce"},
            {"code": "206C(1C)",  "label": "206C(1C) — TCS on Toll Plaza / Parking / Mining"},
            {"code": "206C(1F)",  "label": "206C(1F) — TCS on Motor Vehicle Sale (>₹10L)"},
            {"code": "206C(1G)",  "label": "206C(1G) — TCS on Overseas Remittance / Travel Package"},
            {"code": "206C(1H)",  "label": "206C(1H) — TCS on Sale of Goods (>₹50L)"},
            {"code": "206CCA",    "label": "206CCA — TCS at Higher Rate (non-ITR filers)"},
        ],
    },
}

_QUARTERS = [
    {"value": "Q1", "label": "Q1 (Apr – Jun)"},
    {"value": "Q2", "label": "Q2 (Jul – Sep)"},
    {"value": "Q3", "label": "Q3 (Oct – Dec)"},
    {"value": "Q4", "label": "Q4 (Jan – Mar)"},
]


def _parse_amount(raw: str) -> Decimal:
    cleaned = re.sub(r"[^\d.]", "", str(raw or "0"))
    try:
        return Decimal(cleaned) if cleaned else Decimal("0")
    except Exception:
        return Decimal("0")


_DATE_FORMATS = ["%d-%b-%Y", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d"]


def _parse_date_str(raw: str | None) -> str | None:
    """Convert any supported date string to ISO YYYY-MM-DD that Pydantic accepts."""
    if not raw:
        return None
    from datetime import datetime
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None  # let Pydantic error with the original value


def _normalize_challan(challan_json: dict) -> dict:
    """Flatten nested {fields, tax_breakup, document} structure into flat ChallanData fields.

    The stored challanData from extract_to_json() has:
      - fields["name"]           → ChallanData.deductor_name
      - fields["major_head"]     → full string like "Income Tax (Other than Companies) (0021)"
      - fields["date_of_deposit"]→ "29-May-2026" style strings
      - tax_breakup["Tax"]       → ChallanData.tax (comma-formatted string)
    """
    if "fields" not in challan_json:
        return challan_json  # already flat

    fields = challan_json["fields"]
    tax = challan_json.get("tax_breakup", {})

    # Extract 4-digit major_head code from full string, e.g. "(0021)"
    major_raw = fields.get("major_head", "")
    mh = re.search(r"\((\d{4})\)", major_raw)
    major_head = mh.group(1) if mh else (re.sub(r"\D", "", major_raw)[:4] or "0021")

    # Extract 3-digit minor_head code from full string, e.g. "(200)"
    minor_raw = fields.get("minor_head", "")
    mn = re.search(r"\((\d{3})\)", minor_raw)
    minor_head = mn.group(1) if mn else (re.sub(r"\D", "", minor_raw)[:3] or "200")

    def _str_amount(raw: str) -> str:
        return re.sub(r"[^\d.]", "", str(raw or "0")) or "0"

    result = {
        **fields,
        # name → deductor_name
        "deductor_name": fields.get("name", fields.get("deductor_name", "")),
        # parsed head codes
        "major_head": major_head,
        "minor_head": minor_head,
        # tax breakup — strip commas so Pydantic Decimal coercion works
        "tax":          _str_amount(tax.get("Tax",          tax.get("tax",          "0"))),
        "surcharge":    _str_amount(tax.get("Surcharge",    tax.get("surcharge",    "0"))),
        "cess":         _str_amount(tax.get("Cess",         tax.get("cess",         "0"))),
        "interest":     _str_amount(tax.get("Interest",     tax.get("interest",     "0"))),
        "penalty":      _str_amount(tax.get("Penalty",      tax.get("penalty",      "0"))),
        "fee_234e":     _str_amount(tax.get("Fee under section 234E", tax.get("fee_234e", "0"))),
        "total_amount": _str_amount(tax.get("Total",        tax.get("total_amount", "0"))),
    }

    # Parse dates into ISO format
    for date_field in ("date_of_deposit", "tender_date"):
        parsed = _parse_date_str(result.get(date_field))
        if parsed is not None:
            result[date_field] = parsed
        elif date_field in result:
            del result[date_field]  # remove unparseable → Pydantic uses None default

    return result


# ---------------------------------------------------------------------------
# 0a. Form registry
# ---------------------------------------------------------------------------

@router.get("/forms", summary="Get TDS/TCS form types with sections and quarter options")
async def get_forms():
    return {"status": "success", "forms": _FORM_REGISTRY, "quarters": _QUARTERS}


@router.get("/forms/{form_key}", summary="Get detailed metadata for a specific TDS/TCS form")
async def get_form_detail(form_key: str):
    key = form_key.upper()
    form = _FORM_REGISTRY.get(key)
    if not form:
        raise HTTPException(404, f"Form {form_key!r} not found. Available: {list(_FORM_REGISTRY.keys())}")
    return {"status": "success", "form_key": key, "form": form, "quarters": _QUARTERS}


# ---------------------------------------------------------------------------
# 0b. Compare challan totals vs deductee list
# ---------------------------------------------------------------------------

@router.post("/compare", summary="Compare challan tax vs deductee TDS totals; returns auto-fill data")
async def compare_returns(payload: dict):
    """
    Body:
      {
        "challan": {
          "fields":     { ...snake_case extracted fields... },
          "tax_breakup": { "Tax": "26,130", "Surcharge": "0", ... }
        },
        "deductees": [ { "pan": "...", "tds_deducted": 10, ... }, ... ]
      }
    """
    try:
        challan   = payload.get("challan", {})
        fields    = challan.get("fields", {})
        tax_brkup = challan.get("tax_breakup", {})
        deductees = payload.get("deductees", [])

        # Sum deductee TDS
        deductee_total = Decimal("0")
        for d in deductees:
            raw = d.get("tds_deducted")
            if raw is not None:
                try:
                    deductee_total += Decimal(str(raw)).quantize(Decimal("0.01"))
                except Exception:
                    pass

        challan_tax   = _parse_amount(tax_brkup.get("Tax", "0"))
        challan_total = _parse_amount(tax_brkup.get("Total", "0"))
        surcharge     = _parse_amount(tax_brkup.get("Surcharge", "0"))
        cess          = _parse_amount(tax_brkup.get("Cess", "0"))
        interest      = _parse_amount(tax_brkup.get("Interest", "0"))
        difference    = deductee_total - challan_tax

        errors: list[str] = []
        warnings: list[str] = []

        if abs(difference) > Decimal("0.01"):
            errors.append(
                f"TDS mismatch — deductees total ₹{deductee_total} vs challan tax ₹{challan_tax} "
                f"(difference ₹{abs(difference)})"
            )

        valid_deductees = [d for d in deductees if d.get("pan") and len(str(d.get("pan", ""))) == 10]
        low_tds = [d for d in valid_deductees if 0 < float(d.get("tds_deducted") or 0) < 100]
        if low_tds:
            warnings.append(f"{len(low_tds)} deductee(s) have TDS below ₹100 — verify if correct")

        invalid_pan = [d for d in deductees if not d.get("pan") or len(str(d.get("pan", ""))) != 10]
        if invalid_pan:
            warnings.append(f"{len(invalid_pan)} row(s) skipped — missing or invalid PAN")

        auto_fill = {
            "deductor_tan":        fields.get("tan", ""),
            "deductor_name":       fields.get("name", ""),
            "assessment_year":     fields.get("assessment_year", ""),
            "financial_year":      fields.get("financial_year", ""),
            "major_head":          fields.get("major_head", ""),
            "minor_head":          fields.get("minor_head", ""),
            "nature_of_payment":   fields.get("nature_of_payment", ""),
            "bsr_code":            fields.get("bsr_code", ""),
            "challan_date":        fields.get("date_of_deposit", ""),
            "challan_no":          fields.get("challan_no", ""),
            "cin":                 fields.get("cin", ""),
            "bank_name":           fields.get("bank_name", ""),
            "total_tax_deposited": str(challan_tax),
            "total_with_interest": str(challan_total),
            "surcharge":           str(surcharge),
            "cess":                str(cess),
            "interest":            str(interest),
            "deductee_count":      len(valid_deductees),
            "deductees":           valid_deductees,
        }

        return {
            "status": "success",
            "match": {
                "tds_match":         abs(difference) <= Decimal("0.01"),
                "deductee_total_tds": str(deductee_total),
                "challan_tax":        str(challan_tax),
                "difference":         str(difference),
            },
            "validation": {
                "is_valid": len(errors) == 0,
                "errors":   errors,
                "warnings": warnings,
            },
            "auto_fill": auto_fill,
        }
    except KeyError as exc:
        raise HTTPException(400, f"Missing field: {exc}")
    except Exception as exc:
        logger.error(f"Compare error: {exc}")
        raise HTTPException(422, str(exc))


# ---------------------------------------------------------------------------
# 1. Upload & extract challan PDF
# ---------------------------------------------------------------------------

@router.post("/upload/challan", summary="Extract challan data from PDF")
async def upload_challan(file: UploadFile = File(...)):
    _validate_upload(file, {".pdf"})
    save_path = _save_upload(file, suffix=".pdf")
    try:
        data = _challan_extractor.extract_to_json(save_path)
        return {"status": "success", "challan": data}
    except Exception as exc:
        logger.error(f"Challan extraction error: {exc}")
        raise HTTPException(422, f"Could not extract challan: {exc}")


# ---------------------------------------------------------------------------
# 2. Upload & extract salary / deductee Excel
# ---------------------------------------------------------------------------

@router.post("/upload/excel", summary="Extract deductee records from Excel")
async def upload_excel(
    file: UploadFile = File(...),
    tds_type: Literal["salary", "professional", "rent"] = Form("salary"),
):
    _validate_upload(file, {".xlsx", ".xls", ".xlsm"})
    save_path = _save_upload(file, suffix=Path(file.filename or "data.xlsx").suffix)
    try:
        records = _excel_extractor.extract_to_json(save_path, tds_type=tds_type)
        return {"status": "success", "count": len(records), "deductees": records}
    except Exception as exc:
        logger.error(f"Excel extraction error: {exc}")
        raise HTTPException(422, f"Could not extract Excel: {exc}")


# ---------------------------------------------------------------------------
# 3. Prepare Annexure I / II preview (synchronous, no file written)
# ---------------------------------------------------------------------------

@router.post("/prepare", summary="Build Annexure I/II preview from challan + deductees")
async def prepare_return(payload: dict):
    """
    Body:
      {
        "tds_type": "salary" | "professional" | "rent",
        "quarter": "Q4",
        "challan": { ...ChallanData fields... },
        "deductees": [ ...DeducteeRecord fields... ],
        "deductor": { ...DeductorMeta fields... }
      }
    """
    try:
        tds_type = payload.get("tds_type", "salary")
        quarter = payload.get("quarter", "Q4")
        challan = ChallanData(**payload["challan"])
        deductees = [DeducteeRecord(**d) for d in payload["deductees"]]
        deductor_meta = payload["deductor"]

        validation = _validator.validate_challan(challan)

        if tds_type == "salary":
            processor = Form24QProcessor()
            return_data = processor.build(challan, deductees, deductor_meta, quarter)
            annexure_i = processor.build_annexure_i(return_data)
            annexure_ii = processor.build_annexure_ii(return_data)
        else:
            processor = Form26QProcessor()
            return_data = processor.build(challan, deductees, deductor_meta, quarter)
            annexure_i = processor.build_annexure_i(return_data)
            annexure_ii = []

        return {
            "status": "success",
            "validation": {
                "is_valid": validation.is_valid,
                "errors": validation.errors,
                "warnings": validation.warnings,
            },
            "summary": {
                "form_type": return_data.form_type,
                "financial_year": return_data.financial_year,
                "quarter": return_data.quarter,
                "total_challans": return_data.total_challans,
                "total_tax_deposited": float(return_data.total_tax_deposited),
                "deductee_count": len(deductees),
            },
            "annexure_i": annexure_i,
            "annexure_ii": annexure_ii,
        }
    except KeyError as exc:
        raise HTTPException(400, f"Missing field: {exc}")
    except Exception as exc:
        logger.error(f"Prepare error: {exc}")
        raise HTTPException(422, str(exc))


# ---------------------------------------------------------------------------
# 4a. Generate CSI file — OLTAS format (.csi)
# ---------------------------------------------------------------------------

@router.post("/generate/csi", summary="Generate OLTAS .csi challan status inquiry file")
async def generate_csi(payload: dict):
    """
    Body:
      {
        "challan": { ...ChallanData fields... },
        "status": "F",            ← F=Final, P=Provisional (default F)
        "output_filename": "..."  ← optional, defaults to challan_NNNNN.csi
      }

    CSI line format (comma-separated):
      BSR,TenderDate(DDMMYYYY),ChallanNo,Amount(Rs),MajorHead,TAN,Name,MinorHead,Section,Status

    Example for the ICICI challan:
      6390009,29052026,12188,26923,0021,HYDD06852G,DEUS IT SOLUTIONS PRIVATE LIMITED,200,92B,F
    """
    try:
        challan_json = payload["challan"]
        status = payload.get("status", "F")
        filename = payload.get("output_filename") or \
            f"challan_{challan_json.get('challan_no', 'unknown')}.csi"

        task = generate_csi_file.delay(challan_json, filename, status)
        return {"status": "queued", "task_id": task.id, "filename": filename}
    except KeyError as exc:
        raise HTTPException(400, f"Missing field: {exc}")
    except Exception as exc:
        logger.error(f"CSI generate error: {exc}")
        raise HTTPException(500, str(exc))


@router.post("/generate/csi/sync", summary="Generate OLTAS .csi file synchronously (no Celery required)")
async def generate_csi_sync(payload: dict):
    try:
        from features.tds.generators.csi_generator import CSIGenerator
        from features.tds.schemas.challan import ChallanData

        challan_json = payload["challan"]
        flat = _normalize_challan(challan_json)
        status = payload.get("status", "F")
        filename = payload.get("output_filename") or \
            f"challan_{flat.get('challan_no', 'unknown')}.csi"

        challan = ChallanData(**flat)
        content = CSIGenerator().generate_from_challan(challan, status=status)

        output_path = Path(settings.output_dir) / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")

        return {"status": "success", "filename": filename, "file_path": str(output_path)}
    except KeyError as exc:
        raise HTTPException(400, f"Missing field: {exc}")
    except Exception as exc:
        logger.error(f"CSI sync generate error: {exc}")
        raise HTTPException(500, str(exc))


# ---------------------------------------------------------------------------
# 4b. Generate FVU return file — NSDL pipe-delimited (.txt)
# ---------------------------------------------------------------------------

@router.post("/generate/fvu", summary="Generate NSDL FVU return file (.txt) via Celery")
async def generate_fvu(payload: dict):
    """
    Body:
      {
        "tds_type": "salary" | "professional" | "rent",
        "quarter": "Q4",
        "challan": { ...ChallanData fields... },
        "deductees": [ ...DeducteeRecord fields... ],
        "deductor": { ...DeductorMeta fields... },
        "output_filename": "..."  ← optional
      }
    """
    try:
        tds_type = payload.get("tds_type", "salary")
        quarter = payload.get("quarter", "Q4")
        challan_json = payload["challan"]
        deductees_json = payload["deductees"]
        deductor_meta = payload["deductor"]
        filename = payload.get("output_filename") or \
            f"TDS_{tds_type}_{quarter}_{uuid.uuid4().hex[:8]}.txt"

        if tds_type == "salary":
            task = generate_24q_fvu.delay(challan_json, deductees_json, deductor_meta, filename)
        else:
            task = generate_26q_fvu.delay(challan_json, deductees_json, deductor_meta, filename)

        return {"status": "queued", "task_id": task.id, "filename": filename}
    except KeyError as exc:
        raise HTTPException(400, f"Missing field: {exc}")
    except Exception as exc:
        logger.error(f"FVU generate error: {exc}")
        raise HTTPException(500, str(exc))


@router.post("/generate/fvu/sync", summary="Generate NSDL FVU .txt file synchronously (no Celery required)")
async def generate_fvu_sync(payload: dict):
    try:
        from features.tds.generators.fvu_generator import CSIGenerator as FVUGenerator
        from features.tds.processors.form_24q import Form24QProcessor
        from features.tds.processors.form_26q import Form26QProcessor
        from features.tds.schemas.challan import ChallanData
        from features.tds.schemas.deductee import DeducteeRecord

        tds_type = payload.get("tds_type", "salary")
        quarter = payload.get("quarter", "Q4")
        challan_json = payload["challan"]
        deductees_json = payload["deductees"]
        deductor_meta = payload["deductor"]
        filename = payload.get("output_filename") or \
            f"TDS_{tds_type}_{quarter}_{uuid.uuid4().hex[:8]}.txt"

        challan = ChallanData(**_normalize_challan(challan_json))
        deductees = [DeducteeRecord(**d) for d in deductees_json]
        generator = FVUGenerator()

        if tds_type == "salary":
            return_data = Form24QProcessor().build(challan, deductees, deductor_meta)
            content = generator.generate_24q(return_data)
        else:
            return_data = Form26QProcessor().build(challan, deductees, deductor_meta)
            content = generator.generate_26q(return_data)

        output_path = Path(settings.output_dir) / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")

        return {"status": "success", "filename": filename, "file_path": str(output_path)}
    except KeyError as exc:
        raise HTTPException(400, f"Missing field: {exc}")
    except Exception as exc:
        logger.error(f"FVU sync generate error: {exc}")
        raise HTTPException(500, str(exc))


# ---------------------------------------------------------------------------
# 5. Poll task status
# ---------------------------------------------------------------------------

@router.get("/status/{task_id}", summary="Poll Celery task status")
async def task_status(task_id: str):
    result = AsyncResult(task_id)
    response = {"task_id": task_id, "status": result.status}
    if result.ready():
        response["result"] = result.result
    return response


# ---------------------------------------------------------------------------
# 6. Download generated file (.csi or .txt)
# ---------------------------------------------------------------------------

@router.get("/download/{task_id}", summary="Download generated .csi or .txt file")
async def download_file(task_id: str):
    result = AsyncResult(task_id)
    if not result.ready():
        raise HTTPException(202, "File generation still in progress")
    if result.failed():
        raise HTTPException(500, "File generation failed")

    task_result = result.result or {}
    file_path = task_result.get("file_path")
    if not file_path or not Path(file_path).exists():
        raise HTTPException(404, "Output file not found")

    return FileResponse(
        path=file_path,
        media_type="application/octet-stream",
        filename=Path(file_path).name,
    )


@router.get("/download/file/{filename}", summary="Download a generated file by filename")
async def download_file_by_name(filename: str):
    file_path = Path(settings.output_dir) / filename
    if not file_path.exists():
        raise HTTPException(404, f"File {filename!r} not found")
    return FileResponse(
        path=str(file_path),
        media_type="application/octet-stream",
        filename=filename,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_upload(file: UploadFile, allowed: set[str]) -> None:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in allowed:
        raise HTTPException(400, f"File type {ext!r} not allowed. Expected: {allowed}")
    if file.size and file.size > settings.max_file_size:
        raise HTTPException(413, "File too large")


def _save_upload(file: UploadFile, suffix: str) -> Path:
    dest = Path(settings.upload_dir) / f"{uuid.uuid4().hex}{suffix}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(file.file.read())
    return dest
