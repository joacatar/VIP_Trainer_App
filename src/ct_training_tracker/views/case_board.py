"""Shared case-board helpers for trainer and trainee portals."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from ct_training_tracker.routing import query_value, set_query


def file_progress(requirements: object) -> str:
    if not isinstance(requirements, list):
        return "0 sent · 3 to send"
    sent = 0
    accepted = 0
    to_send = 0
    for requirement in requirements:
        if not isinstance(requirement, dict):
            continue
        status = requirement.get("status")
        if status == "accepted":
            accepted += 1
        elif status in {"submitted", "under_review"}:
            sent += 1
        elif status in {"missing", "replacement_requested"}:
            to_send += 1
    if to_send:
        return f"{sent + accepted} sent · {to_send} to send"
    if accepted == 3:
        return "3/3 accepted"
    return f"{sent} sent · {accepted} accepted"


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


def case_label(row: dict[str, Any] | pd.Series) -> str:
    return (
        f"Case {row['case_no']} · {row['status']} · "
        f"due {row['due_date'] or '—'} · {row['files']}"
    )


def select_case_from_list(
    frame: pd.DataFrame,
    *,
    key_prefix: str,
    trainee_id: str | None = None,
) -> dict[str, Any] | None:
    """Render a left-side case list and return the selected enriched row."""
    if frame.empty:
        st.info("No cases found.")
        return None

    set_no = st.radio(
        "Set",
        options=[1, 2],
        format_func=lambda value: f"Set {value}",
        horizontal=True,
        key=f"{key_prefix}_set",
    )
    set_frame = frame.loc[frame["set_no"] == set_no].copy()
    if set_frame.empty:
        st.caption("No cases in this set.")
        return None

    rows = set_frame.to_dict(orient="records")
    options = [row["id"] for row in rows]
    by_id = {row["id"]: row for row in rows}

    requested = query_value("case")
    if requested in by_id:
        index = options.index(requested)
    else:
        set_query(trainee=trainee_id, case=options[0])
        st.rerun()

    selected_id = st.radio(
        "Cases",
        options=options,
        index=index,
        format_func=lambda value: case_label(by_id[value]),
        label_visibility="collapsed",
        key=f"{key_prefix}_case_list_{set_no}",
    )

    if selected_id != query_value("case"):
        set_query(trainee=trainee_id, case=selected_id)
        st.rerun()

    return by_id[selected_id]


def render_case_summary(row: dict[str, Any]) -> None:
    st.subheader(f"Set {row['set_no']} · Case {row['case_no']}")
    st.caption(f"Case id: `{row['id']}`")
    meta = st.columns(3)
    meta[0].markdown(f"**Status**  \n{row['status']}")
    meta[1].markdown(f"**Due date**  \n{row['due_date'] or '—'}")
    meta[2].markdown(f"**Files**  \n{row['files']}")
    if row.get("notes"):
        st.info(row["notes"])
