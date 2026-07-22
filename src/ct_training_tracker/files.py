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
    "pdf_primary": (".pdf",),
    "pdf_secondary": (".pdf",),
    # Compound Arthrex extension — match by endswith, not Path.suffix alone.
    "ov": (".ov-arthrex",),
}


def sanitize_filename(filename: str) -> str:
    cleaned = Path(filename).name.strip().replace(" ", "_")
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "", cleaned)
    return cleaned or "upload.bin"


def extension_matches(filename: str, allowed: tuple[str, ...]) -> bool:
    lowered = Path(filename).name.lower()
    return any(lowered.endswith(ext.lower()) for ext in allowed)


def validate_upload(kind: str, filename: str) -> str:
    allowed = ALLOWED_EXTENSIONS.get(kind, ())
    if not allowed or not extension_matches(filename, allowed):
        labels = ", ".join(sorted(allowed)) or "an allowed type"
        raise ValueError(
            f"{FILE_KIND_LABELS.get(kind, kind)} must end with {labels} "
            f"(got {Path(filename).name!r})"
        )
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
