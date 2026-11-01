"""Celery tasks for extracting TDS data from uploaded files."""

from pathlib import Path

from loguru import logger

from workers.celery_app import celery_app
from features.tds.extractors.challan_extractor import ChallanExtractor
from features.tds.extractors.excel_extractor import ExcelExtractor


@celery_app.task(
    bind=True,
    name="workers.tasks.tds.extraction_tasks.extract_challan",
    max_retries=3,
    default_retry_delay=5,
)
def extract_challan(self, file_path: str) -> dict:
    """Extract challan data from an Income Tax Department PDF challan receipt."""
    try:
        logger.info(f"Extracting challan from: {file_path}")
        extractor = ChallanExtractor()
        result = extractor.extract_to_json(Path(file_path))
        logger.info(f"Challan extracted: TAN={result.get('tan')}, BSR={result.get('bsr_code')}")
        return {"status": "success", "data": result}
    except Exception as exc:
        logger.error(f"Challan extraction failed: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="workers.tasks.tds.extraction_tasks.extract_salary_excel",
    max_retries=3,
    default_retry_delay=5,
)
def extract_salary_excel(self, file_path: str, tds_type: str = "salary") -> dict:
    """Extract deductee records from a salary breakup Excel sheet."""
    try:
        logger.info(f"Extracting Excel [{tds_type}] from: {file_path}")
        extractor = ExcelExtractor()
        records = extractor.extract_to_json(Path(file_path), tds_type=tds_type)
        logger.info(f"Excel extracted: {len(records)} records")
        return {"status": "success", "count": len(records), "data": records}
    except Exception as exc:
        logger.error(f"Excel extraction failed: {exc}")
        raise self.retry(exc=exc)
