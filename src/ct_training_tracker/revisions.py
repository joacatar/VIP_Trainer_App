"""Fixed review sections and revision helpers."""

from __future__ import annotations

from typing import Any

REVIEW_SECTIONS: tuple[tuple[str, str, int], ...] = (
    ("scan", "Scan", 1),
    ("rider_form", "Rider form", 2),
    ("segmentation", "Segmentation", 3),
    ("scapula", "Scapula", 4),
    ("glenoid_landmark", "Glenoid landmark", 5),
    ("humeral_landmark", "Humeral landmark", 6),
    ("humeral_implant", "Humeral implant", 7),
    ("glenoid_implant", "Glenoid implant", 8),
)

SECTION_LABELS = {key: label for key, label, _ in REVIEW_SECTIONS}
REVISION_START_STATUSES = {"in_review", "corrections_sent"}


def section_label(section_key: str) -> str:
    return SECTION_LABELS.get(section_key, section_key.replace("_", " ").title())


def can_start_revision(case_status: str) -> bool:
    return case_status in REVISION_START_STATUSES


def open_corrections(corrections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in corrections if row.get("status") == "open"]


def count_open_corrections_in_tree(revision: dict[str, Any]) -> int:
    total = 0
    for section in revision.get("revision_sections") or []:
        if not isinstance(section, dict):
            continue
        for correction in section.get("corrections") or []:
            if isinstance(correction, dict) and correction.get("status") == "open":
                total += 1
    return total
