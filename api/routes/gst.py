"""
GST invoice extraction API routes.

Endpoints:
  POST /extract/sync      → extract + validate PDF/image synchronously
  POST /extract           → queue Celery extraction task → task_id
  POST /export/excel      → extract + export color-coded Excel (sync, streaming download)
  GET  /status/{task_id}  → poll Celery task
  GET  /download/{task_id} → download Excel from completed Celery task
"""

import uuid
from pathlib import Path

from celery.result import AsyncResult
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from loguru import logger

from config.settings import get_settings
from features.gst.exporters.excel_exporter import ExcelExporter
from features.gst.processors.invoice_processor import InvoiceProcessor
from workers.tasks.gst.extraction_tasks import extract_invoices

settings = get_settings()
router = APIRouter()
_processor = InvoiceProcessor()
_exporter = ExcelExporter()

_ALLOWED_EXTS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}


# ---------------------------------------------------------------------------
# 1. Extract synchronously
# ---------------------------------------------------------------------------

@router.post("/extract/sync", summary="Extract GST invoices synchronously (no Celery required)")
async def extract_sync(file: UploadFile = File(...)):
    _validate_upload(file)
    save_path = _save_upload(file)
    try:
        result = _processor.process_to_json(save_path)
        return {"status": "success", "result": result}
    except Exception as exc:
        logger.error(f"GST sync extraction error: {exc}")
        raise HTTPException(422, f"Extraction failed: {exc}")


# ---------------------------------------------------------------------------
# 2. Extract asynchronously via Celery
# ---------------------------------------------------------------------------

@router.post("/extract", summary="Queue GST invoice extraction via Celery")
async def extract_async(file: UploadFile = File(...)):
    _validate_upload(file)
    save_path = _save_upload(file)
    try:
        task = extract_invoices.delay(str(save_path))
        return {"status": "queued", "task_id": task.id, "file": file.filename}
    except Exception as exc:
        logger.error(f"GST task queue error: {exc}")
        raise HTTPException(500, str(exc))


# ---------------------------------------------------------------------------
# 3. Extract + export Excel synchronously
# ---------------------------------------------------------------------------

@router.post("/export/excel", summary="Extract GST invoices and download color-coded Excel")
async def export_excel(file: UploadFile = File(...)):
    _validate_upload(file)
    save_path = _save_upload(file)
    try:
        result = _processor.process(save_path)
        stem = Path(file.filename or "invoices").stem
        output_filename = f"gst_{stem}_{uuid.uuid4().hex[:8]}.xlsx"
        output_path = Path(settings.output_dir) / output_filename
        _exporter.export(result, output_path)
        return FileResponse(
            path=str(output_path),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=output_filename,
        )
    except Exception as exc:
        logger.error(f"GST Excel export error: {exc}")
        raise HTTPException(500, f"Export failed: {exc}")


# ---------------------------------------------------------------------------
# 4. Poll Celery task
# ---------------------------------------------------------------------------

@router.get("/status/{task_id}", summary="Poll Celery GST task status")
async def task_status(task_id: str):
    result = AsyncResult(task_id)
    response = {"task_id": task_id, "status": result.status}
    if result.ready():
        response["result"] = result.result
    return response


# ---------------------------------------------------------------------------
# 5. Download Excel from completed Celery task
# ---------------------------------------------------------------------------

@router.get("/download/{task_id}", summary="Download Excel from completed Celery extraction task")
async def download_file(task_id: str):
    result = AsyncResult(task_id)
    if not result.ready():
        raise HTTPException(202, "Task still in progress")
    if result.failed():
        raise HTTPException(500, "Task failed")

    task_result = result.result or {}
    file_path = task_result.get("file_path")
    if not file_path or not Path(file_path).exists():
        raise HTTPException(404, "Output file not found")

    return FileResponse(
        path=file_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=Path(file_path).name,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_upload(file: UploadFile) -> None:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXTS:
        raise HTTPException(400, f"File type {ext!r} not allowed. Accepted: {_ALLOWED_EXTS}")
    if file.size and file.size > settings.max_file_size:
        raise HTTPException(413, "File exceeds the 10 MB size limit")


def _save_upload(file: UploadFile) -> Path:
    ext = Path(file.filename or "file.pdf").suffix.lower()
    dest = Path(settings.upload_dir) / f"{uuid.uuid4().hex}{ext}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(file.file.read())
    return dest
