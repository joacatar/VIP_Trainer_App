"""Trainee portal views — next-up dashboard and case workspace."""

from __future__ import annotations

import datetime as dt

import streamlit as st

from ct_training_tracker.case_labels import case_title
from ct_training_tracker.components.progress_journey import render_progress_journey
from ct_training_tracker.components.ui import (
    render_empty_state,
    render_page_header,
)
from ct_training_tracker.metrics import count_file_waiting
from ct_training_tracker.models import Profile
from ct_training_tracker.repository import TrainingRepository
from ct_training_tracker.routing import query_value
from ct_training_tracker.views.case_board import (
    apply_case_filter,
    enrich_cases,
    pick_next_case,
    render_case_summary,
    sort_case_rows,
)
from ct_training_tracker.views.case_files import render_trainee_case_uploads
from ct_training_tracker.views.questions import (
    render_ask_question_entry,
    render_home_ask_question,
    render_trainee_questions,
)
from ct_training_tracker.views.resources import render_case_resources_readonly
from ct_training_tracker.views.revisions import render_trainee_revisions


def _due_is_urgent(due_raw: object, today: dt.date) -> bool:
    if not due_raw:
        return False
    try:
        due = dt.date.fromisoformat(str(due_raw)[:10])
    except ValueError:
        return False
    return (due - today).days <= 2


def _format_due(due_raw: object) -> str:
    if not due_raw:
        return "No due date"
    try:
        due = dt.date.fromisoformat(str(due_raw)[:10])
    except ValueError:
        return str(due_raw)
    return f"Due {due.strftime('%b')} {due.day}"


def _coming_up_rows(
    frame,
    *,
    primary_id: str | None,
    limit: int = 3,
):
    if frame is None or frame.empty:
        return []
    needs = apply_case_filter(frame, "needs_you", role="trainee")
    pool = needs if not needs.empty else frame
    ordered = sort_case_rows(pool, role="trainee")
    rows = []
    for _, row in ordered.iterrows():
        if primary_id and str(row["id"]) == str(primary_id):
            continue
        rows.append(row.to_dict())
        if len(rows) >= limit:
            break
    return rows


def _render_next_up_card(row: dict, *, today: dt.date, key_prefix: str) -> None:
    due_raw = row.get("due_date")
    urgent = _due_is_urgent(due_raw, today)
    due_text = _format_due(due_raw)
    title = case_title(row)
    next_step = row.get("next_step") or row.get("status") or "Open case"

    with st.container(border=True):
        st.caption(":blue[NEXT UP]")
        left, right = st.columns([3.2, 1], vertical_alignment="center")
        with left:
            st.markdown(f"**{title}**")
            if urgent:
                st.markdown(f"{next_step} · :orange[**{due_text}**]")
            else:
                st.markdown(f"{next_step} · **{due_text}**")
        with right:
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


def _render_coming_up(rows: list[dict], *, today: dt.date) -> None:
    if not rows:
        return
    for row in rows:
        due_raw = row.get("due_date")
        due_text = _format_due(due_raw)
        label = f"Case {row.get('catalog_label') or row.get('case_no')}"
        step = row.get("next_step") or "—"
        cols = st.columns([3, 1], vertical_alignment="center")
        cols[0].markdown(f"{label} · {step}")
        if _due_is_urgent(due_raw, today):
            cols[1].markdown(f":orange[{due_text}]")
        else:
            cols[1].caption(due_text)


def _render_open_corrections_summary(
    *,
    cases: list[dict],
    threads_by_case: dict[str, list[dict]],
) -> None:
    open_by_case: list[tuple[dict, int]] = []
    for case in cases:
        case_id = str(case["id"])
        open_threads = [
            thread
            for thread in threads_by_case.get(case_id, [])
            if thread.get("status") == "open"
        ]
        if open_threads:
            open_by_case.append((case, len(open_threads)))
    if not open_by_case:
        return

    total = sum(count for _case, count in open_by_case)
    if len(open_by_case) == 1:
        case, count = open_by_case[0]
        label = case_title(case)
        message = f"{count} open correction{'s' if count != 1 else ''} on {label}"
        target_id = str(case["id"])
    else:
        message = (
            f"{total} open corrections across {len(open_by_case)} cases"
        )
        target_id = str(open_by_case[0][0]["id"])

    with st.container(border=True):
        left, right = st.columns([4, 1], vertical_alignment="center")
        left.caption(message)
        if right.button("View", key="trainee_open_corrections_view"):
            st.switch_page(
                "app_pages/trainee_case_workspace.py",
                query_params={"case": target_id},
            )


def render_trainee_portal(
    repository: TrainingRepository,
    profile: Profile,
) -> None:
    today = dt.date.today()
    name = profile["full_name"] or "Trainee"
    st.markdown(f"### Welcome, {name}")
    st.caption("Open your next case, or check what's coming up.")

    trainee = repository.get_trainee_for_user(profile["id"])
    if not trainee:
        st.warning(
            "Your account has not been linked to a trainee record yet. "
            "Ask your trainer to finish the setup."
        )
        return

    unread_answers = repository.count_unread_answers_for_trainee(trainee["id"])
    if unread_answers:
        with st.container(border=True):
            left, right = st.columns([3, 1], vertical_alignment="center")
            left.markdown(
                f"**{unread_answers} new answer"
                f"{'s' if unread_answers != 1 else ''} to your questions**"
            )
            if right.button(
                "Open questions",
                key="open_questions_inbox_banner",
                type="primary",
                width="stretch",
                icon=":material/mark_email_unread:",
            ):
                st.switch_page("app_pages/trainee_questions.py")

    cases = repository.list_cases(trainee["id"], include_files=True)
    assignments = repository.list_homework_for_cases(
        [row["id"] for row in cases]
    )
    frame = enrich_cases(cases, assignments, role="trainee")

    next_case = pick_next_case(frame, role="trainee")
    if next_case is None:
        render_empty_state(
            "No cases yet",
            detail="Ask your trainer to assign your first case.",
        )
    else:
        _render_next_up_card(next_case, today=today, key_prefix="trainee")
        coming = _coming_up_rows(
            frame,
            primary_id=str(next_case["id"]),
            limit=3,
        )
        _render_coming_up(coming, today=today)

    st.markdown("**Your progress**")
    threads_by_case = {
        str(case["id"]): repository.list_correction_threads(str(case["id"]))
        for case in cases
    }
    render_progress_journey(
        cases,
        today=today,
        threads_by_case=threads_by_case,
    )

    _render_open_corrections_summary(
        cases=cases,
        threads_by_case=threads_by_case,
    )

    with st.expander("Ask your trainer", icon=":material/help:"):
        render_home_ask_question(
            repository,
            user_id=profile["id"],
            cases=cases,
            key_prefix="trainee_dashboard_ask",
        )


def render_trainee_case_workspace(
    repository: TrainingRepository,
    profile: Profile,
) -> None:
    """Render the full-width trainee workspace for their selected case."""
    trainee = repository.get_trainee_for_user(profile["id"])
    case_id = query_value("case")
    if not trainee or not case_id:
        render_empty_state(
            "Select a case from the inbox to view its workspace.",
            detail="Use My cases to pick a case, then open the workspace.",
        )
        if st.button("Back to my cases", icon=":material/arrow_back:"):
            st.switch_page("app_pages/trainee_cases.py")
        return

    case = repository.get_case(case_id, include_files=True)
    if case is None:
        st.error("This case is unavailable or the link is no longer valid.")
        if st.button("Back to my cases", icon=":material/arrow_back:"):
            st.switch_page("app_pages/trainee_cases.py")
        return

    assignments = repository.list_homework_for_cases([case_id])
    selected = enrich_cases([case], assignments, role="trainee").iloc[0].to_dict()
    back, heading = st.columns([1, 5], vertical_alignment="center")
    with back:
        if st.button("Back", icon=":material/arrow_back:"):
            st.switch_page(
                "app_pages/trainee_cases.py",
                query_params={"case": case_id},
            )
    with heading:
        render_page_header(
            "Case workspace",
            "Complete files, read feedback, or ask a question.",
        )

    render_case_summary(selected)
    render_case_resources_readonly(repository, case_id=case_id)
    file_counts = count_file_waiting([case])
    files_tab, review_tab, questions_tab = st.tabs(
        [
            ":material/folder: Files",
            ":material/rate_review: Feedback",
            ":material/help: Questions",
        ],
        key=f"trainee_case_tabs_{case_id}",
        on_change="rerun",
    )
    if files_tab.open:
        with files_tab:
            st.caption(
                f"Package {file_counts.sent} ready · {file_counts.to_send} to send · "
                f"{file_counts.accepted} accepted"
            )
            trainer_name = repository.get_trainer_display_name_for_trainee(
                trainee["id"]
            )
            render_trainee_case_uploads(
                repository,
                user_id=profile["id"],
                case=case,
                trainer_name=trainer_name,
            )
    if review_tab.open:
        with review_tab:
            render_ask_question_entry(
                repository,
                user_id=profile["id"],
                case=case,
                key_prefix="trainee_feedback_ask",
                default_scope="section",
            )
            render_trainee_revisions(repository, case=case)
    if questions_tab.open:
        with questions_tab:
            render_trainee_questions(
                repository, user_id=profile["id"], case=case
            )
