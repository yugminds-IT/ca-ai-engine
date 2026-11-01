"""Celery tasks for generating TDS return files.

Two distinct output formats:
  • CSI  (.csi) — OLTAS Challan Status Inquiry format (comma-separated challan rows).
                  Used to verify/share challan details; importable into RPU.
  • FVU  (.txt) — NSDL FVU-compatible pipe-delimited return file (BH/CD/DD/BT records).
                  Submitted to NSDL after FVU validation.
"""

from pathlib import Path

from loguru import logger

from workers.celery_app import celery_app
from features.tds.processors.form_24q import Form24QProcessor
from features.tds.processors.form_26q import Form26QProcessor
from features.tds.generators.csi_generator import CSIGenerator
from features.tds.generators.fvu_generator import CSIGenerator as FVUGenerator
from features.tds.schemas.challan import ChallanData
from features.tds.schemas.deductee import DeducteeRecord
from config.settings import get_settings

settings = get_settings()


# ---------------------------------------------------------------------------
# CSI file tasks (OLTAS format — .csi)
# ---------------------------------------------------------------------------

@celery_app.task(
    bind=True,
    name="workers.tasks.tds.generation_tasks.generate_csi_file",
    max_retries=2,
)
def generate_csi_file(
    self,
    challan_json: dict,
    output_filename: str,
    status: str = "F",
) -> dict:
    """Generate an OLTAS .csi file from a single challan."""
    try:
        logger.info("Generating CSI (OLTAS) file")
        challan = ChallanData(**challan_json)

        generator = CSIGenerator()
        content = generator.generate_from_challan(challan, status=status)

        output_path = Path(settings.output_dir) / output_filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")

        logger.info(f"CSI file written: {output_path}")
        return {"status": "success", "file_path": str(output_path)}
    except Exception as exc:
        logger.error(f"CSI generation failed: {exc}")
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# FVU return file tasks (NSDL pipe-delimited format — .txt)
# ---------------------------------------------------------------------------

@celery_app.task(
    bind=True,
    name="workers.tasks.tds.generation_tasks.generate_24q_fvu",
    max_retries=2,
)
def generate_24q_fvu(
    self,
    challan_json: dict,
    deductees_json: list[dict],
    deductor_meta: dict,
    output_filename: str,
) -> dict:
    """Build Form 24Q return and write the FVU-compatible .txt file."""
    try:
        logger.info("Generating Form 24Q FVU return file")

        challan = ChallanData(**challan_json)
        deductees = [DeducteeRecord(**d) for d in deductees_json]

        processor = Form24QProcessor()
        return_data = processor.build(challan, deductees, deductor_meta)

        generator = FVUGenerator()
        content = generator.generate_24q(return_data)

        output_path = Path(settings.output_dir) / output_filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")

        logger.info(f"Form 24Q FVU file written: {output_path}")
        return {"status": "success", "file_path": str(output_path)}
    except Exception as exc:
        logger.error(f"24Q FVU generation failed: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="workers.tasks.tds.generation_tasks.generate_26q_fvu",
    max_retries=2,
)
def generate_26q_fvu(
    self,
    challan_json: dict,
    deductees_json: list[dict],
    deductor_meta: dict,
    output_filename: str,
) -> dict:
    """Build Form 26Q return (professional income / rent) and write the FVU file."""
    try:
        logger.info("Generating Form 26Q FVU return file")

        challan = ChallanData(**challan_json)
        deductees = [DeducteeRecord(**d) for d in deductees_json]

        processor = Form26QProcessor()
        return_data = processor.build(challan, deductees, deductor_meta)

        generator = FVUGenerator()
        content = generator.generate_26q(return_data)

        output_path = Path(settings.output_dir) / output_filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")

        logger.info(f"Form 26Q FVU file written: {output_path}")
        return {"status": "success", "file_path": str(output_path)}
    except Exception as exc:
        logger.error(f"26Q FVU generation failed: {exc}")
        raise self.retry(exc=exc)
