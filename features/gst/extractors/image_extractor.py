"""
Extract structured GST invoice fields from an image using SmolVLM
(HuggingFaceTB/SmolVLM-256M-Instruct) — CPU-friendly vision-language model.

  - AutoModelForImageTextToText + AutoProcessor from HuggingFace
  - apply_chat_template (text prompt) + processor(text, images) → model.generate → JSON parse
  - Model is loaded once per process (singleton)
"""

import ast
import io
import json
import re
import threading
from decimal import Decimal, InvalidOperation

import torch
from PIL import Image
from loguru import logger
from transformers import AutoModelForImageTextToText, AutoProcessor

from config.settings import get_settings

_MODEL_PATH = get_settings().vlm_model_path

# Singleton state — loaded once per process, thread-safe via _lock
_lock = threading.Lock()
_processor = None
_model = None

# Prompt uses a filled-in example object so the 256M model doesn't copy
# the field descriptions verbatim — just fill the values in the same shape.
_SCHEMA_PROMPT = (
    "Look at this invoice image and extract the following fields.\n"
    "Return ONLY a valid JSON object using these exact key names, no extra text:\n"
    "{\n"
    '  "GSTIN NO": "",\n'
    '  "Invoice no.": "",\n'
    '  "Invoice date": "",\n'
    '  "Party name": "",\n'
    '  "Taxable value": 0,\n'
    '  "CGST": 0,\n'
    '  "SGST": 0,\n'
    '  "IGST": 0,\n'
    '  "Total": 0\n'
    "}\n"
    "Rules:\n"
    "- Invoice date must be in DD-MM-YYYY format\n"
    "- All amount fields must be plain numbers only (no commas, no ₹ symbol)\n"
    "- If a field is not visible, use empty string or 0\n"
    "- Output nothing except the JSON object"
)

# Canonical key → output field name (keys normalised to lowercase for matching)
_KEY_MAP = {
    "gstin no":      "gstin",
    "gstin no.":     "gstin",
    "invoice no.":   "invoice_no",
    "invoice no":    "invoice_no",
    "invoice number":"invoice_no",
    "invoice date":  "invoice_date",
    "party name":    "party_name",
    "taxable value": "taxable_value",
    "cgst":          "cgst",
    "sgst":          "sgst",
    "igst":          "igst",
    "total":         "total",
}


def _get_device_and_dtype() -> tuple[str, torch.dtype]:
    if torch.cuda.is_available():
        return "cuda", torch.float16
    if torch.backends.mps.is_available():
        return "mps", torch.bfloat16
    return "cpu", torch.float32


def _load_model():
    """Load SmolVLM exactly once per process (double-checked locking)."""
    global _processor, _model
    if _model is not None:
        return _processor, _model
    with _lock:
        if _model is not None:
            return _processor, _model
        device, dtype = _get_device_and_dtype()
        logger.info(f"Loading {_MODEL_PATH} on {device} ({dtype}) — first-time only …")
        _processor = AutoProcessor.from_pretrained(_MODEL_PATH)
        _model = AutoModelForImageTextToText.from_pretrained(
            _MODEL_PATH, dtype=dtype, device_map=device
        )
        logger.info("SmolVLM model ready")
    return _processor, _model


def _safe_decimal(val: object) -> Decimal:
    if val in (None, "", "-"):
        return Decimal("0")
    # If the model returned a list, take the first numeric element
    if isinstance(val, list):
        val = next((v for v in val if isinstance(v, (int, float))), 0)
    try:
        cleaned = re.sub(r"[^\d.]", "", str(val))
        return Decimal(cleaned) if cleaned else Decimal("0")
    except InvalidOperation:
        return Decimal("0")


def _parse_json(text: str) -> dict | None:
    """Parse the first JSON-like object from model output.

    Tries strict JSON first, then falls back to ast.literal_eval so that
    Python-dict-style output (single quotes, trailing commas) is also handled.
    """
    text = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.MULTILINE).strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        logger.debug(f"No JSON object found in model output: {text!r}")
        return None
    snippet = m.group(0)
    try:
        return json.loads(snippet)
    except json.JSONDecodeError:
        pass
    # Fallback: model used single quotes or Python-dict syntax
    try:
        result = ast.literal_eval(snippet)
        if isinstance(result, dict):
            return result
    except (ValueError, SyntaxError):
        pass
    logger.debug(f"Could not parse model output as JSON or dict: {snippet!r}")
    return None


class ImageExtractor:
    """
    OCR a single invoice image via SmolVLM and return parsed fields.

    The HuggingFace model is loaded once on first use and shared across all
    instances — initialising this class is cheap.
    """

    def extract(self, image_bytes: bytes) -> dict:
        """
        Run SmolVLM on PNG/JPEG bytes and return invoice field dict.

        Returned keys: gstin, invoice_no, invoice_date, party_name,
        taxable_value, cgst, sgst, igst, total  (Decimal for amounts).
        """
        processor, model = _load_model()

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        msgs = [
            {
                "role": "user",
                "content": [
                    {"type": "image"},
                    {"type": "text", "text": _SCHEMA_PROMPT},
                ],
            }
        ]

        prompt = processor.apply_chat_template(msgs, add_generation_prompt=True)

        inputs = processor(
            text=prompt,
            images=[image],
            return_tensors="pt",
        ).to(model.device)

        inputs.pop("token_type_ids", None)

        with torch.inference_mode():
            gen = model.generate(**inputs, max_new_tokens=512, do_sample=False)

        raw = processor.decode(
            gen[0][inputs["input_ids"].shape[1]:],
            skip_special_tokens=True,
        )
        logger.debug(f"Raw model output: {raw!r}")

        return self._map_fields(_parse_json(raw) or {})

    def _map_fields(self, data: dict) -> dict:
        """Remap model keys → InvoiceData field names (case-insensitive) and coerce types."""
        # Normalise all keys to lowercase so casing differences don't matter
        normalised = {k.lower().strip(): v for k, v in data.items()}

        def get(field: str):
            return normalised.get(_KEY_MAP.get(field, field))

        return {
            "gstin":         str(get("gstin no") or "").strip().upper(),
            "invoice_no":    str(get("invoice no.") or "").strip(),
            "invoice_date":  str(get("invoice date") or "").strip(),
            "party_name":    str(get("party name") or "").strip(),
            "taxable_value": _safe_decimal(get("taxable value")),
            "cgst":          _safe_decimal(get("cgst")),
            "sgst":          _safe_decimal(get("sgst")),
            "igst":          _safe_decimal(get("igst")),
            "total":         _safe_decimal(get("total")),
        }
