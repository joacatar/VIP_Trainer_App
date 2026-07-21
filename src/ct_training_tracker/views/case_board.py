"""Shared case-board helpers for trainer and trainee portals."""

from typing import Any

import pandas as pd


def file_progress(requirements: object) -> str:
    if not isinstance(requirements, list):
        return "0 / 3 accepted"
    accepted = sum(
        requirement.get("status") == "accepted"
        for requirement in requirements
        if isinstance(requirement, dict)
    )
    return f"{accepted} / 3 accepted"


def homework_by_case_id(
    assignments: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Map assignments keyed by case_id when available, else set-case."""
    mapping: dict[str, dict[str, Any]] = {}
    for assignment in assignments:
        case_id = assignment.get("case_id")
        if case_id:
            mapping[str(case_id)] = assignment
            continue
        case = assignment.get("cases")
        if isinstance(case, dict):
            mapping[f"{case['set_no']}-{case['case_no']}"] = assignment
    return mapping


def enrich_cases(
    cases: list[dict[str, Any]],
    assignments: list[dict[str, Any]],
) -> pd.DataFrame:
    homework = homework_by_case_id(assignments)
    rows: list[dict[str, Any]] = []
    for case in cases:
        assignment = homework.get(str(case["id"]))
        if assignment is None:
            assignment = homework.get(f"{case['set_no']}-{case['case_no']}")
        rows.append(
            {
                "id": case["id"],
                "set_no": case["set_no"],
                "case_no": case["case_no"],
                "status": str(case["status"]).replace("_", " ").title(),
                "due_date": case.get("due_date") or case.get("schedule_due_date"),
                "schedule_due_date": case.get("schedule_due_date"),
                "files": file_progress(case.get("file_requirements")),
                "notes": (assignment or {}).get("instructions") or "",
                "raw_status": case["status"],
            }
        )
    return pd.DataFrame(rows)


def visible_case_frame(frame: pd.DataFrame, set_no: int) -> pd.DataFrame:
    set_frame = frame.loc[frame["set_no"] == set_no].copy()
    return set_frame[["case_no", "status", "due_date", "files", "notes"]].rename(
        columns={
            "case_no": "Case",
            "status": "Status",
            "due_date": "Due date",
            "files": "Files",
            "notes": "Notes",
        }
    )
