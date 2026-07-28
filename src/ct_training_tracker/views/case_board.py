"""Shared case-board helpers for trainer and trainee portals."""

from __future__ import annotations

from typing import Any, Literal

import pandas as pd
import streamlit as st

from ct_training_tracker.case_labels import (
    case_catalog_label,
    case_label,
    case_order_number,
    case_title,
)
from ct_training_tracker.components.ui import render_case_header, status_color
from ct_training_tracker.metrics import (
    AppRole,
    case_owner,
    next_step,
    owned_by_statuses,
    waiting_on_other_statuses,
)
from ct_training_tracker.routing import query_value, set_query

CaseFilter = Literal["needs_you", "with_other", "all"]


def filter_labels(role: AppRole) -> dict[CaseFilter, str]:
    other = "With trainee" if role == "trainer" else "With trainer"
    return {
        "needs_you": "Needs you",
        "with_other": other,
        "all": "All",
    }


def file_progress(requirements: object) -> str:
    if not isinstance(requirements, list):
        return "0 ready · 3 to send"
    ready = 0
    accepted = 0
    to_send = 0
    with_trainer = 0
    for requirement in requirements:
        if not isinstance(requirement, dict):
            continue
        status = requirement.get("status")
        if status == "accepted":
            accepted += 1
        elif status == "under_review":
            with_trainer += 1
        elif status == "submitted":
            ready += 1
        elif status in {"missing", "replacement_requested"}:
            to_send += 1
    if with_trainer:
        return f"{with_trainer}/3 with trainer"
    if to_send:
        return f"{ready + accepted} ready · {to_send} to send"
    if accepted == 3:
        return "3/3 accepted"
    if ready == 3:
        return "3/3 ready — submit package"
    return f"{ready} ready · {accepted} accepted"


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
    *,
    role: AppRole = "trainee",
) -> pd.DataFrame:
    homework = homework_by_case_id(assignments)
    rows: list[dict[str, Any]] = []
    for case in cases:
        assignment = homework.get(str(case["id"]))
        if assignment is None:
            assignment = homework.get(f"{case['set_no']}-{case['case_no']}")
        raw_status = str(case["status"])
        rows.append(
            {
                "id": case["id"],
                "set_no": case["set_no"],
                "case_no": case["case_no"],
                "catalog_label": case_catalog_label(case),
                "order_number": case_order_number(case),
                "status": raw_status.replace("_", " ").title(),
                "due_date": case.get("due_date") or case.get("schedule_due_date"),
                "schedule_due_date": case.get("schedule_due_date"),
                "files": file_progress(case.get("file_requirements")),
                "notes": (assignment or {}).get("instructions") or "",
                "raw_status": raw_status,
                "owner": case_owner(raw_status),
                "next_step": next_step(raw_status, role=role),
            }
        )
    return pd.DataFrame(rows)


def filter_priority(raw_status: str, *, role: AppRole) -> int:
    if raw_status in owned_by_statuses(role):
        return 0
    if raw_status in waiting_on_other_statuses(role):
        return 1
    if raw_status == "not_started":
        return 2
    if raw_status == "approved":
        return 3
    return 4


def apply_case_filter(
    frame: pd.DataFrame,
    case_filter: CaseFilter,
    *,
    role: AppRole = "trainee",
) -> pd.DataFrame:
    if frame.empty:
        return frame
    if case_filter == "needs_you":
        return frame.loc[
            frame["raw_status"].isin(owned_by_statuses(role))
        ].copy()
    if case_filter == "with_other":
        return frame.loc[
            frame["raw_status"].isin(waiting_on_other_statuses(role))
        ].copy()
    return frame.copy()


def sort_case_rows(
    frame: pd.DataFrame,
    *,
    role: AppRole = "trainee",
) -> pd.DataFrame:
    if frame.empty:
        return frame
    ordered = frame.copy()
    ordered["_priority"] = ordered["raw_status"].map(
        lambda status: filter_priority(str(status), role=role)
    )
    ordered["_due"] = ordered["due_date"].fillna("9999-99-99")
    return ordered.sort_values(
        ["_priority", "_due", "set_no", "case_no"],
        kind="mergesort",
    ).drop(columns=["_priority", "_due"])


def pick_next_case(
    frame: pd.DataFrame,
    *,
    role: AppRole = "trainee",
) -> dict[str, Any] | None:
    """Prefer the earliest case that still needs this role."""
    if frame.empty:
        return None
    needs = apply_case_filter(frame, "needs_you", role=role)
    pool = needs if not needs.empty else frame
    row = sort_case_rows(pool, role=role).iloc[0]
    return row.to_dict()


def _render_case_row(
    row: dict[str, Any],
    *,
    selected: bool,
    key: str,
) -> bool:
    """Compact scannable case row. Returns True when clicked."""
    with st.container(border=True):
        title_col, badge_col = st.columns([2.1, 1.1], vertical_alignment="center")
        clicked = title_col.button(
            case_label(row),
            key=key,
            type="primary" if selected else "secondary",
            width="content",
        )
        with badge_col:
            st.badge(
                str(row["status"]),
                color=status_color(str(row.get("raw_status") or "")),
            )
        st.caption(
            f"{row.get('next_step') or '—'} · Due {row.get('due_date') or '—'} · "
            f"{row.get('files')}"
        )
    return clicked


def select_case_from_list(
    frame: pd.DataFrame,
    *,
    key_prefix: str,
    role: AppRole,
    trainee_id: str | None = None,
    default_filter: CaseFilter = "needs_you",
) -> dict[str, Any] | None:
    """Render a compact filtered case inbox and return the selected row."""
    if frame.empty:
        st.info("No cases found.")
        return None

    labels = filter_labels(role)
    with st.container(horizontal=True, gap="small"):
        set_no = st.segmented_control(
            "Set",
            options=[1, 2],
            format_func=lambda value: f"Set {value}",
            default=1,
            key=f"{key_prefix}_set",
            label_visibility="collapsed",
            width="content",
        )
        filter_key = st.segmented_control(
            "Show",
            options=list(labels),
            format_func=lambda value: labels[value],
            default=default_filter,
            key=f"{key_prefix}_filter",
            label_visibility="collapsed",
            width="content",
        )
    if set_no is None:
        set_no = 1
    if filter_key is None:
        filter_key = "all"

    set_frame = frame.loc[frame["set_no"] == set_no].copy()
    filtered = sort_case_rows(
        apply_case_filter(set_frame, filter_key, role=role),
        role=role,
    )

    needs_count = len(apply_case_filter(set_frame, "needs_you", role=role))
    waiting_count = len(apply_case_filter(set_frame, "with_other", role=role))
    counts = st.columns(3)
    counts[0].caption(f"{len(set_frame)} in set")
    counts[1].caption(f"{needs_count} need you")
    counts[2].caption(
        f"{waiting_count} "
        f"{'with trainee' if role == 'trainer' else 'with trainer'}"
    )

    all_in_set = {
        row["id"]: row for row in set_frame.to_dict(orient="records")
    }
    if not all_in_set:
        st.caption("No cases in this set.")
        return None

    rows = filtered.to_dict(orient="records")
    by_id = {row["id"]: row for row in rows}

    if filtered.empty:
        if filter_key == "needs_you":
            st.caption(
                "Nothing needs you in this set. Try "
                f"{labels['with_other']} or All."
            )
        elif filter_key == "with_other":
            st.caption("No cases waiting on the other person in this set.")
        else:
            st.caption("No cases in this set.")

    requested = query_value("case")
    if requested not in all_in_set:
        default_pool = rows or sort_case_rows(set_frame, role=role).to_dict(
            orient="records"
        )
        set_query(trainee=trainee_id, case=default_pool[0]["id"])
        st.rerun()

    if requested not in by_id and requested in all_in_set:
        st.caption("Selected case is hidden by the current filter.")

    for row in rows:
        case_id = row["id"]
        if _render_case_row(
            row,
            selected=case_id == requested,
            key=f"{key_prefix}_case_{set_no}_{case_id}",
        ):
            if case_id != requested:
                set_query(trainee=trainee_id, case=case_id)
                st.rerun()

    return all_in_set.get(requested)


def render_next_case_card(
    row: dict[str, Any] | None,
    *,
    key_prefix: str,
    trainee_id: str | None = None,
) -> None:
    """Highlight the single most important case for the trainee."""
    del trainee_id
    if row is None:
        return
    with st.container(border=True):
        st.markdown("**Your next case**")
        title, action = st.columns([2.4, 1], vertical_alignment="center")
        with title:
            st.write(case_title(row))
            st.caption(
                f"{row.get('next_step') or row['status']} · "
                f"Due {row.get('due_date') or '—'} · {row.get('files')}"
            )
        with action:
            if st.button(
                "Open",
                key=f"{key_prefix}_open_next",
                type="primary",
                width="stretch",
                icon=":material/arrow_forward:",
            ):
                st.switch_page(
                    "app_pages/trainee_case_workspace.py",
                    query_params={"case": row["id"]},
                )


def render_case_summary(row: dict[str, Any]) -> None:
    render_case_header(row)
