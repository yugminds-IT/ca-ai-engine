"""Celery tasks for GST invoice extraction and Excel export."""

import uuid
from pathlib import Path

from loguru import logger

from config.settings import get_settings
from workers.celery_app import celery_app

settings = get_settings()


@celery_app.task(
    bind=True,
    name="workers.tasks.gst.extraction_tasks.extract_invoices",
    max_retries=3,
    default_retry_delay=5,
)
def extract_invoices(self, file_path: str) -> dict:
    """Extract, validate, and export GST invoices from a PDF or image file."""
    try:
        from features.gst.exporters.excel_exporter import ExcelExporter
        from features.gst.processors.invoice_processor import InvoiceProcessor

        processor = InvoiceProcessor()
        exporter = ExcelExporter()

        result = processor.process(file_path)

        stem = Path(file_path).stem
        output_filename = f"gst_{stem}_{uuid.uuid4().hex[:8]}.xlsx"
        output_path = Path(settings.output_dir) / output_filename
        exporter.export(result, output_path)

        logger.info(
            f"GST task complete: {result.total_invoices} invoice(s), "
            f"output: {output_filename}"
        )

        return {
            "status": "success",
            "file_path": str(output_path),
            "filename": output_filename,
            "summary": {
                "source_file":    result.source_file,
                "total_pages":    result.total_pages,
                "total_invoices": result.total_invoices,
                "ok_count":       result.ok_count,
                "review_count":   result.review_count,
                "error_count":    result.error_count,
            },
            "data": result.model_dump(mode="json"),
        }
    except Exception as exc:
        logger.error(f"GST extraction task failed for {file_path}: {exc}")
        raise self.retry(exc=exc)
