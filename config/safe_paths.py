"""Keeps caller-supplied file names inside the output folder."""

import re
from pathlib import Path

from config.settings import get_settings


def safe_file_name(name: object, default: str = "output") -> str:
    """Only the last path part, only letters, digits, dot, dash and underscore, no leading dot."""
    base = Path(str(name or "")).name
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base).lstrip(".")
    return base[:120] or default


def output_file(name: object, default: str = "output") -> Path:
    """A path inside settings.output_dir for this name. Never escapes the folder."""
    root = Path(get_settings().output_dir).resolve()
    path = (root / safe_file_name(name, default)).resolve()
    if path.parent != root:
        raise ValueError("Invalid file name")
    return path
