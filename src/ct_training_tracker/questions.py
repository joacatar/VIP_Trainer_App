"""Question helpers for trainee Q&A threads."""

from __future__ import annotations

from typing import Any

from ct_training_tracker.revisions import SECTION_LABELS, section_label

QUESTION_STATUSES = ("open", "answered", "resolved")
OPEN_INBOX_STATUSES = frozenset({"open"})


def question_section_label(section_key: str | None) -> str:
    if not section_key:
        return "General"
    return section_label(section_key)


def question_status_label(status: str) -> str:
    return str(status).replace("_", " ").title()


def count_open_questions(rows: list[dict[str, Any]]) -> int:
    return sum(1 for row in rows if row.get("status") in OPEN_INBOX_STATUSES)


def section_options() -> list[tuple[str | None, str]]:
    options: list[tuple[str | None, str]] = [(None, "General (whole case)")]
    for key, label in SECTION_LABELS.items():
        options.append((key, label))
    return options
