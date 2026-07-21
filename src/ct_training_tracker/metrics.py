from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ProgressTotals:
    trainees: int
    total_cases: int
    approved_cases: int
    overdue_cases: int
    total_files: int
    accepted_files: int


def summarize_progress(rows: list[dict[str, Any]]) -> ProgressTotals:
    return ProgressTotals(
        trainees=len(rows),
        total_cases=sum(int(row["total_cases"]) for row in rows),
        approved_cases=sum(int(row["approved_cases"]) for row in rows),
        overdue_cases=sum(int(row["overdue_cases"]) for row in rows),
        total_files=sum(int(row["total_files"]) for row in rows),
        accepted_files=sum(int(row["accepted_files"]) for row in rows),
    )
