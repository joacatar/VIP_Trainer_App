"""File naming and validation helpers for case uploads."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

FILE_KIND_LABELS = {
    "pdf_primary": "PDF 1",
    "pdf_secondary": "PDF 2",
    "ov": "OV",
}

READY_SLOT_STATUSES = frozenset({"submitted", "under_review"})
PACKAGE_EDITABLE_STATUSES = frozenset(
    {"assigned", "submitted", "awaiting_resubmission"}
)
PACKAGE_WITH_TRAINER_STATUSES = frozenset({"in_review", "corrections_sent"})

ALLOWED_EXTENSIONS = {
    "pdf_primary": (".pdf",),
    "pdf_secondary": (".pdf",),
    # Compound Arthrex extension — match by endswith, not Path.suffix alone.
    "ov": (".ov-arthrex",),
}

SCREENSHOT_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif")


def slot_is_ready(status: str) -> bool:
    return status in READY_SLOT_STATUSES


def count_ready_slots(requirements: list[dict[str, Any]]) -> int:
    return sum(
        1
        for row in requirements
        if isinstance(row, dict) and slot_is_ready(str(row.get("status") or ""))
    )


def can_submit_package(
    case_status: str,
    requirements: list[dict[str, Any]],
) -> bool:
    if case_status not in PACKAGE_EDITABLE_STATUSES:
        return False
    if any(
        isinstance(row, dict) and row.get("status") == "replacement_requested"
        for row in requirements
    ):
        return False
    return count_ready_slots(requirements) >= 3


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


def validate_screenshot(filename: str) -> str:
    if not extension_matches(filename, SCREENSHOT_EXTENSIONS):
        labels = ", ".join(SCREENSHOT_EXTENSIONS)
        raise ValueError(
            f"Screenshot must end with {labels} (got {Path(filename).name!r})"
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


def screenshot_storage_path(
    *,
    owner_user_id: str,
    case_id: str,
    correction_id: str,
    filename: str,
) -> str:
    """Store under the trainee auth user folder so they can download via RLS."""
    safe_name = validate_screenshot(filename)
    return f"{owner_user_id}/{case_id}/screenshots/{correction_id}/{safe_name}"


def question_screenshot_storage_path(
    *,
    owner_user_id: str,
    case_id: str,
    question_id: str,
    filename: str,
) -> str:
    safe_name = validate_screenshot(filename)
    return (
        f"{owner_user_id}/{case_id}/question-screenshots/"
        f"{question_id}/{safe_name}"
    )
