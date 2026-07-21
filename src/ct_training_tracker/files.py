"""File naming and validation helpers for case uploads."""

from __future__ import annotations

import re
from pathlib import Path

FILE_KIND_LABELS = {
    "pdf_primary": "PDF 1",
    "pdf_secondary": "PDF 2",
    "ov": "OV",
}

ALLOWED_EXTENSIONS = {
    "pdf_primary": {".pdf"},
    "pdf_secondary": {".pdf"},
    "ov": {".ov"},
}


def sanitize_filename(filename: str) -> str:
    cleaned = Path(filename).name.strip().replace(" ", "_")
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "", cleaned)
    return cleaned or "upload.bin"


def validate_upload(kind: str, filename: str) -> str:
    extension = Path(filename).suffix.lower()
    allowed = ALLOWED_EXTENSIONS.get(kind, set())
    if extension not in allowed:
        labels = ", ".join(sorted(allowed))
        raise ValueError(f"{FILE_KIND_LABELS.get(kind, kind)} must be {labels}")
    return sanitize_filename(filename)


def storage_object_path(
    *,
    user_id: str,
    case_id: str,
    kind: str,
    version_no: int,
    filename: str,
) -> str:
    safe_name = validate_upload(kind, filename)
    return f"{user_id}/{case_id}/{kind}/v{version_no}_{safe_name}"
