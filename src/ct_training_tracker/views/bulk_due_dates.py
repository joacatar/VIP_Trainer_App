"""Case multi-select helpers for bulk due-date updates."""

from __future__ import annotations

import datetime as dt
from typing import Any

import streamlit as st
from postgrest.exceptions import APIError

from ct_training_tracker.case_labels import case_catalog_label
from ct_training_tracker.data_cache import invalidate_trainer_cache
from ct_training_tracker.repository import TrainingRepository

SELECTION_KEY = "_case_bulk_selection"
SELECT_MODE_KEY = "cases_select_mode"
DRAFT_DATES_KEY = "_case_bulk_draft_dates"


def selected_case_ids() -> set[str]:
    raw = st.session_state.get(SELECTION_KEY)
    if not isinstance(raw, set):
        raw = set()
        st.session_state[SELECTION_KEY] = raw
    return raw


def clear_selection() -> None:
    st.session_state[SELECTION_KEY] = set()
    st.session_state.pop(DRAFT_DATES_KEY, None)


def toggle_case_selected(case_id: str, *, selected: bool) -> None:
    ids = selected_case_ids()
    if selected:
        ids.add(case_id)
    else:
        ids.discard(case_id)
    st.session_state[SELECTION_KEY] = ids


def is_select_mode() -> bool:
    return bool(st.session_state.get(SELECT_MODE_KEY, False))


def render_selection_controls() -> None:
    """Select toggle for the Cases page header (count/Clear live in the panel)."""
    st.toggle(
        "Select",
        key=SELECT_MODE_KEY,
        help="Select cases across trainees to bulk-update due dates.",
    )


def clear_selection_if_leaving_cases() -> None:
    """Drop bulk selection when the trainer navigates away from Cases."""
    clear_selection()
    st.session_state[SELECT_MODE_KEY] = False


def render_bulk_due_date_panel(
    repository: TrainingRepository,
    cases_by_id: dict[str, dict[str, Any]],
) -> None:
    """Quick-apply + per-case date rows + commit, matching the v2 mockup."""
    ids = sorted(selected_case_ids())
    if not ids:
        return

    drafts: dict[str, dt.date] = st.session_state.setdefault(DRAFT_DATES_KEY, {})
    for case_id in ids:
        if case_id not in drafts:
            case = cases_by_id.get(case_id) or {}
            raw = case.get("due_date") or case.get("schedule_due_date")
            try:
                drafts[case_id] = (
                    dt.date.fromisoformat(str(raw)[:10])
                    if raw
                    else dt.date.today()
                )
            except ValueError:
                drafts[case_id] = dt.date.today()

    with st.container(border=True):
        head = st.columns([3, 1], vertical_alignment="center")
        head[0].markdown(f"**{len(ids)} cases selected**")
        if head[1].button("Clear", key="bulk_panel_clear"):
            clear_selection()
            st.rerun()

        st.markdown("Set due date for all selected")
        apply_cols = st.columns([2, 1], vertical_alignment="bottom")
        quick = apply_cols[0].date_input(
            "Bulk date",
            value=dt.date.today(),
            key="bulk_quick_date",
            label_visibility="collapsed",
        )
        if apply_cols[1].button("Apply to all", key="bulk_apply_all"):
            for case_id in ids:
                drafts[case_id] = quick
            st.session_state[DRAFT_DATES_KEY] = drafts
            st.rerun()

        for case_id in ids:
            case = cases_by_id.get(case_id) or {"id": case_id}
            label = (
                f"Case {case_catalog_label(case)}"
                if case.get("set_no")
                else case_id
            )
            trainee = case.get("trainee_name") or "Trainee"
            with st.container(border=True):
                st.markdown(f"**{label}**")
                st.caption(trainee)
                drafts[case_id] = st.date_input(
                    "Due date",
                    value=drafts[case_id],
                    key=f"bulk_due_{case_id}",
                    label_visibility="collapsed",
                )

        if st.button(
            f"Update due dates for {len(ids)} cases",
            type="primary",
            width="stretch",
            key="bulk_commit",
        ):
            updates = [(case_id, drafts[case_id]) for case_id in ids]
            try:
                failed = repository.bulk_update_due_dates(updates)
            except APIError as exc:
                st.error(exc.message)
                return
            if failed:
                st.error(
                    "Updated some cases, but these failed: "
                    + ", ".join(failed)
                )
                # Keep failed ids selected so the trainer can retry.
                selected_case_ids().difference_update(
                    {case_id for case_id, _ in updates if case_id not in failed}
                )
            else:
                st.toast(f"Updated due dates for {len(ids)} cases")
                clear_selection()
            invalidate_trainer_cache()
            st.rerun()
