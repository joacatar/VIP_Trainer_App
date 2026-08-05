import datetime as dt

import pandas as pd
import streamlit as st
from postgrest.exceptions import APIError

from ct_training_tracker.case_labels import case_title
from ct_training_tracker.components.ui import (
    constrained_width,
    render_case_header,
    render_compact_review_header,
    render_empty_state,
    render_page_header,
)
from ct_training_tracker.data_cache import (
    cached_active_trainees,
    cached_homework_for_cases,
    cached_trainee_cases,
    invalidate_trainer_cache,
)
from ct_training_tracker.metrics import (
    case_attention_state,
    count_file_waiting,
    waiting_label,
)
from ct_training_tracker.models import Profile
from ct_training_tracker.repository import TrainingRepository
from ct_training_tracker.resource_rules import build_system_resources
from ct_training_tracker.routing import query_value, set_query
from ct_training_tracker.trainee_filters import (
    SHOW_TEST_TRAINEES_KEY,
    filter_trainees,
    trainee_display_name,
)
from ct_training_tracker.views.case_board import (
    enrich_cases,
    render_case_summary,
    select_case_from_list,
)
from ct_training_tracker.views.case_files import render_trainer_case_review
from ct_training_tracker.views.kanban import render_case_board
from ct_training_tracker.views.metrics import render_training_analytics
from ct_training_tracker.views.questions import (
    render_trainer_case_questions,
    render_trainer_question_inbox,
)
from ct_training_tracker.views.resources import render_case_resources_editor
from ct_training_tracker.views.revisions import render_trainer_revisions


def render_dashboard(repository: TrainingRepository) -> None:
    render_page_header(
        "Training overview",
        "Start with what needs you, then scan trainee progress.",
    )
    include_test = st.toggle(
        "Show test trainees",
        key=SHOW_TEST_TRAINEES_KEY,
        help="Practice accounts tagged as Test stay hidden unless this is on.",
    )

    rows = filter_trainees(
        repository.list_progress(),
        include_test=include_test,
    )
    if not rows:
        if include_test:
            st.info(
                "No trainees yet. Add the first trainee to generate their 32 cases."
            )
        else:
            st.info(
                "No live trainees to show. Turn on **Show test trainees** to see "
                "practice accounts, or add a real trainee."
            )
        return

    # Same source of truth as the Cases page filters: case_attention_state
    # over each trainee's (cached) case list, so counts can never disagree.
    counts_by_trainee = {
        str(row["trainee_id"]): _trainee_attention_counts(
            repository, str(row["trainee_id"])
        )
        for row in rows
    }
    need_review = sum(c["in_review"] for c in counts_by_trainee.values())
    overdue_total = sum(c["overdue"] for c in counts_by_trainee.values())
    to_send_total = sum(c["to_send"] for c in counts_by_trainee.values())
    approved_total = sum(c["approved"] for c in counts_by_trainee.values())
    cases_total = sum(c["total"] for c in counts_by_trainee.values())
    open_questions = repository.count_open_questions()

    question_word = "open question" if open_questions == 1 else "open questions"
    st.markdown(
        f":blue[**{need_review}** need review] · "
        f":red[**{overdue_total}** overdue] · "
        f":gray[**{to_send_total}** awaiting trainee] · "
        f":orange[**{open_questions}** {question_word}]"
    )
    done_ratio = approved_total / cases_total if cases_total else 0.0
    bar_col, caption_col = st.columns([4, 1], vertical_alignment="center")
    bar_col.progress(done_ratio)
    caption_col.caption(f"{approved_total} of {cases_total} approved")

    attention_tab, analytics_tab = st.tabs(
        ["Needs attention", "Performance & forecast"],
        key="dashboard_tabs",
        on_change="rerun",
    )
    if attention_tab.open:
        with attention_tab:
            _render_attention_feed(repository, rows, counts_by_trainee)
    if analytics_tab.open:
        with analytics_tab:
            _render_all_trainees_table(rows)
            render_training_analytics(repository, include_test=include_test)


def _trainee_attention_counts(
    repository: TrainingRepository,
    trainee_id: str,
) -> dict[str, int]:
    """Per-trainee actionable counts from case_attention_state."""
    cases = cached_trainee_cases(repository, trainee_id, include_files=True)
    today = dt.date.today()
    in_review = 0
    overdue = 0
    approved = 0
    for case in cases:
        attention = case_attention_state(case, [], [], [], today)
        if attention.state == "needs_trainer":
            in_review += 1
        if attention.overdue:
            overdue += 1
        if attention.state == "approved":
            approved += 1
    return {
        "in_review": in_review,
        "overdue": overdue,
        "to_send": count_file_waiting(cases).to_send,
        "approved": approved,
        "total": len(cases),
    }


def _render_attention_feed(
    repository: TrainingRepository,
    rows: list[dict],
    counts_by_trainee: dict[str, dict[str, int]],
) -> None:
    """One card per trainee with actionable chips, then the open questions."""
    for row in sorted(
        rows,
        key=lambda item: (
            -counts_by_trainee[str(item["trainee_id"])]["in_review"],
            -counts_by_trainee[str(item["trainee_id"])]["overdue"],
            -counts_by_trainee[str(item["trainee_id"])]["to_send"],
        ),
    ):
        counts = counts_by_trainee[str(row["trainee_id"])]
        in_review = counts["in_review"]
        overdue = counts["overdue"]
        to_send = counts["to_send"]
        chips: list[str] = []
        if in_review:
            chips.append(f":blue-badge[{in_review} in review]")
        if overdue:
            chips.append(f":red-badge[{overdue} overdue]")
        if to_send:
            chips.append(f":gray-badge[{to_send} files to send]")
        with st.container(border=True):
            left, right = st.columns([3, 1], vertical_alignment="center")
            with left:
                st.markdown(f"**{trainee_display_name(row)}**")
                st.markdown(
                    " ".join(chips) if chips else ":green-badge[All clear]"
                )
            if right.button(
                "Open cases",
                key=f"open_cases_{row['trainee_id']}",
                type="primary",
                width="stretch",
                icon=":material/arrow_forward:",
            ):
                st.switch_page(
                    "app_pages/trainer_cases.py",
                    query_params={"trainee": row["trainee_id"]},
                )

    render_trainer_question_inbox(repository)


def _render_all_trainees_table(rows: list[dict]) -> None:
    frame = pd.DataFrame(rows)
    frame["display_name"] = frame.apply(trainee_display_name, axis=1)
    frame["case_progress"] = (
        frame["approved_cases"].astype(str) + " / " + frame["total_cases"].astype(str)
    )
    frame["file_progress"] = (
        frame["accepted_files"].astype(str) + " / " + frame["total_files"].astype(str)
    )
    frame["waiting"] = frame.apply(waiting_label, axis=1)
    with st.expander("All trainees", expanded=False):
        st.dataframe(
            frame[
                [
                    "display_name",
                    "current_phase",
                    "case_progress",
                    "file_progress",
                    "waiting",
                    "waiting_on_trainer",
                    "waiting_on_trainee",
                    "overdue_cases",
                    "estimated_completion_date",
                ]
            ].rename(
                columns={
                    "display_name": "Trainee",
                    "current_phase": "Phase",
                    "case_progress": "Cases",
                    "file_progress": "Files",
                    "waiting": "Next action",
                    "waiting_on_trainer": "In review",
                    "waiting_on_trainee": "Still to send",
                    "overdue_cases": "Overdue tasks",
                    "estimated_completion_date": "Est. completion",
                }
            ),
            hide_index=True,
            width="stretch",
        )


def render_trainees(repository: TrainingRepository, user_id: str) -> None:
    render_page_header(
        "Add trainee",
        "Create a trainee profile and generate their scheduled training cases.",
    )
    with constrained_width(560):
        with st.form("add_trainee", clear_on_submit=True, border=True):
            full_name = st.text_input("Full name")
            email = st.text_input("Email")
            start_date = st.date_input("Training start date", value=dt.date.today())
            timezone = st.selectbox(
                "Timezone",
                ["Australia/Sydney", "America/New_York"],
            )
            is_test = st.checkbox(
                "Mark as test trainee",
                help="Hidden from the main dashboard unless Show test trainees is on.",
            )
            st.info(
                "This will automatically create 32 cases and 96 file requirements.",
                icon=":material/info:",
            )
            submitted = st.form_submit_button(
                "Create trainee",
                type="primary",
                width="stretch",
            )

    if not submitted:
        return
    if not full_name.strip():
        st.error("Full name is required.")
        return

    try:
        trainee_id = repository.create_trainee(
            full_name=full_name.strip(),
            email=email.strip() or None,
            start_date=start_date,
            timezone=timezone,
            created_by=user_id,
            is_test=is_test,
        )
    except APIError as exc:
        st.error(f"Could not create trainee: {exc.message}")
        return

    if trainee_id:
        try:
            repository.add_case_resources(
                build_system_resources(repository.list_cases(trainee_id))
            )
        except APIError as exc:
            st.warning(f"Trainee created, but seeding resources failed: {exc.message}")

    invalidate_trainer_cache()
    st.success("Trainee created with 32 scheduled cases and 96 file requirements.")
    st.rerun()


def _assign_case(
    repository: TrainingRepository,
    *,
    case_row: dict,
    show_header: bool = True,
) -> None:
    if case_row["raw_status"] != "not_started":
        return

    schedule_due = dt.date.fromisoformat(str(case_row["schedule_due_date"]))
    with constrained_width(640):
        with st.container(border=True):
            if show_header:
                render_case_header(case_row, bordered=False)
                st.divider()
            else:
                st.markdown("**Assign homework**")
                st.caption(
                    "Set the due date and optional notes. "
                    "This does not open the review workspace."
                )
            with st.form(f"assign_case_{case_row['id']}", border=False):
                due_date = st.date_input(
                    "Due date",
                    value=schedule_due,
                    help="Suggested from the training schedule.",
                )
                notes = st.text_area(
                    "Notes for trainee (optional)",
                    placeholder="Anything they should focus on for this case.",
                )
                submitted = st.form_submit_button(
                    "Assign case",
                    type="primary",
                )

    if not submitted:
        return

    try:
        repository.assign_homework(
            case_id=case_row["id"],
            title=case_title(case_row),
            instructions=notes,
            schedule_due_date=schedule_due,
            due_date=due_date,
        )
    except APIError as exc:
        st.error(f"Could not assign case: {exc.message}")
        return

    invalidate_trainer_cache()
    st.success(f"{case_title(case_row)} assigned.")
    st.rerun()


def render_cases(repository: TrainingRepository, user_id: str) -> None:
    del user_id
    header_col, refresh_col = st.columns([5, 1], vertical_alignment="bottom")
    with header_col:
        render_page_header(
            "Cases",
            "Board is the scan view. Inbox is for assigning homework and "
            "per-trainee detail.",
        )
    with refresh_col:
        if st.button(
            "Refresh",
            icon=":material/refresh:",
            width="stretch",
            help="Reload trainee and case data (auto-refreshes periodically too).",
        ):
            invalidate_trainer_cache()
            st.rerun()
    include_test = st.toggle(
        "Show test trainees",
        key=SHOW_TEST_TRAINEES_KEY,
        help="Practice accounts tagged as Test stay hidden unless this is on.",
    )

    trainees = filter_trainees(
        cached_active_trainees(repository),
        include_test=include_test,
    )
    if not trainees:
        if include_test:
            st.info("Add a trainee first.")
        else:
            st.info(
                "No live trainees. Turn on **Show test trainees** to open practice "
                "accounts, or add a real trainee."
            )
        return

    requested_view = query_value("view") or "board"
    board_label = ":material/view_column: Board"
    inbox_label = ":material/inbox: Inbox"
    default_tab = inbox_label if requested_view == "inbox" else board_label
    board_tab, inbox_tab = st.tabs(
        [board_label, inbox_label],
        key="cases_view_tabs",
        on_change="rerun",
        default=default_tab,
    )

    if board_tab.open:
        with board_tab:
            labels = {row["id"]: trainee_display_name(row) for row in trainees}
            requested_trainee = query_value("trainee")
            options = ["__all__", *labels]
            default_index = 0
            if requested_trainee in labels:
                default_index = options.index(requested_trainee)
            filter_id = st.selectbox(
                "Trainee filter",
                options=options,
                index=default_index,
                format_func=lambda value: (
                    "All trainees" if value == "__all__" else labels[value]
                ),
                key="board_trainee_filter",
            )
            render_case_board(
                repository,
                trainees,
                trainee_filter_id=(
                    None if filter_id == "__all__" else str(filter_id)
                ),
            )

    if inbox_tab.open:
        with inbox_tab:
            _render_cases_inbox(repository, trainees)


def _render_cases_inbox(
    repository: TrainingRepository,
    trainees: list[dict],
) -> None:
    labels = {row["id"]: trainee_display_name(row) for row in trainees}
    trainee_ids = list(labels)
    requested_trainee = query_value("trainee")
    trainee_index = (
        trainee_ids.index(requested_trainee) if requested_trainee in labels else 0
    )

    with constrained_width(420):
        trainee_id = st.selectbox(
            "Trainee",
            options=trainee_ids,
            index=trainee_index,
            format_func=lambda value: labels[value],
            key="inbox_trainee_select",
        )
    if trainee_id != requested_trainee:
        set_query(trainee=trainee_id, case=None, view="inbox")
        st.rerun()

    cases = cached_trainee_cases(repository, trainee_id, include_files=True)
    assignments = cached_homework_for_cases(
        repository, [row["id"] for row in cases]
    )
    frame = enrich_cases(cases, assignments, role="trainer")

    list_col, preview_col = st.columns([1.05, 1.2], gap="large")
    with list_col:
        st.subheader("Case inbox")
        selected = select_case_from_list(
            frame,
            key_prefix="trainer",
            role="trainer",
            trainee_id=trainee_id,
            default_filter="needs_you",
        )
    with preview_col:
        st.subheader("Quick view")
        if selected is None:
            render_empty_state(
                "Select a case from the inbox",
                detail="Unassigned cases stay here for homework. "
                "Submitted packages open in Review.",
            )
            return

        render_case_summary(selected)
        render_case_resources_editor(repository, case_id=str(selected["id"]))
        raw = str(selected.get("raw_status") or "")
        if raw == "not_started":
            st.caption("This case still needs homework assignment.")
            _assign_case(repository, case_row=selected, show_header=False)
            return

        if raw in {"in_review", "corrections_sent"}:
            cta_label = "Open review"
            cta_help = "Review the package, leave feedback, then publish."
        elif raw in {"assigned", "submitted", "awaiting_resubmission"}:
            cta_label = "Open case"
            cta_help = "Trainee is still preparing files. You can inspect progress."
        else:
            cta_label = "Open case"
            cta_help = "View files, feedback history, and questions."

        st.caption(cta_help)
        if st.button(
            cta_label,
            key=f"open_workspace_{selected['id']}",
            type="primary",
            width="content",
            icon=":material/rate_review:",
        ):
            st.switch_page(
                "app_pages/trainer_case_workspace.py",
                query_params={"trainee": trainee_id, "case": selected["id"]},
            )


def render_trainer_case_workspace(
    repository: TrainingRepository,
    user_id: str,
) -> None:
    """Deep review surface — not used for homework assignment."""
    trainee_id = query_value("trainee")
    case_id = query_value("case")
    if not trainee_id or not case_id:
        render_empty_state(
            "Select a case from the inbox to open Review.",
            detail="Assign homework from Cases. Use Review for packages in review.",
        )
        if st.button("Back to cases", icon=":material/arrow_back:"):
            st.switch_page("app_pages/trainer_cases.py")
        return

    case = repository.get_case(case_id, include_files=True)
    if case is None:
        st.error("This case is unavailable or the link is no longer valid.")
        if st.button("Back to cases", icon=":material/arrow_back:"):
            st.switch_page("app_pages/trainer_cases.py")
        return

    trainee = repository.get_trainee(trainee_id)
    assignments = repository.list_homework_for_cases([case_id])
    selected = enrich_cases([case], assignments, role="trainer").iloc[0].to_dict()
    selected["trainee_name"] = (
        trainee.get("full_name") if trainee else "Unknown trainee"
    )
    case["trainee_name"] = selected["trainee_name"]

    if selected["raw_status"] == "not_started":
        render_empty_state(
            "Assign homework from the Cases inbox.",
            detail="Review opens only after the case is assigned.",
            icon=":material/assignment_add:",
        )
        if st.button("Back to Cases", icon=":material/arrow_back:", type="primary"):
            st.switch_page(
                "app_pages/trainer_cases.py",
                query_params={"trainee": trainee_id, "case": case_id},
            )
        return

    back, heading = st.columns([1, 8], vertical_alignment="center")
    with back:
        if st.button(
            "",
            icon=":material/arrow_back:",
            key=f"review_back_{case_id}",
            help="Back to Cases",
        ):
            st.switch_page(
                "app_pages/trainer_cases.py",
                query_params={"trainee": trainee_id, "case": case_id},
            )
    with heading:
        render_compact_review_header(selected)

    files_tab, review_tab, questions_tab = st.tabs(
        [
            ":material/folder: Files",
            ":material/rate_review: Feedback",
            ":material/help: Questions",
        ],
        key=f"trainer_review_tabs_{case_id}",
        on_change="rerun",
        default=":material/rate_review: Feedback",
    )
    if files_tab.open:
        with files_tab:
            render_trainer_case_review(repository, case=case)
    if review_tab.open:
        with review_tab:
            render_trainer_revisions(repository, user_id=user_id, case=case)
    if questions_tab.open:
        with questions_tab:
            render_trainer_case_questions(repository, user_id=user_id, case=case)


def render_trainer_portal(
    repository: TrainingRepository,
    profile: Profile,
) -> None:
    """Legacy single-page portal kept for compatibility."""
    st.sidebar.write(f"Signed in as **{profile['full_name'] or 'Trainer'}**")
    page = st.sidebar.radio(
        "Navigation",
        ["Dashboard", "Cases", "Add trainee"],
    )
    if page == "Dashboard":
        render_dashboard(repository)
    elif page == "Cases":
        render_cases(repository, profile["id"])
    else:
        render_trainees(repository, profile["id"])
