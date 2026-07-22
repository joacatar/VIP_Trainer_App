import datetime as dt

import pandas as pd
import streamlit as st
from postgrest.exceptions import APIError

from ct_training_tracker.components.ui import (
    constrained_width,
    render_case_header,
    render_empty_state,
    render_page_header,
)
from ct_training_tracker.metrics import summarize_progress, waiting_label
from ct_training_tracker.models import Profile
from ct_training_tracker.repository import TrainingRepository
from ct_training_tracker.routing import query_value, set_query
from ct_training_tracker.views.case_board import (
    enrich_cases,
    render_case_summary,
    select_case_from_list,
)
from ct_training_tracker.views.case_files import render_trainer_case_review
from ct_training_tracker.views.questions import (
    render_trainer_case_questions,
    render_trainer_question_inbox,
)
from ct_training_tracker.views.revisions import render_trainer_revisions


def render_dashboard(repository: TrainingRepository) -> None:
    render_page_header(
        "Training overview",
        "Start with what needs you, then scan trainee progress.",
    )
    rows = repository.list_progress()
    if not rows:
        st.info("No trainees yet. Add the first trainee to generate their 32 cases.")
        return

    totals = summarize_progress(rows)
    open_questions = repository.count_open_questions()

    with st.container(horizontal=True, gap="small"):
        st.metric(
            "Needs review",
            totals.waiting_on_trainer,
            help="Packages waiting for your revision or send-back.",
            border=True,
        )
        st.metric(
            "Overdue",
            totals.overdue_cases,
            help="Cases past due that are not approved yet.",
            border=True,
        )
        st.metric(
            "Awaiting trainee",
            totals.waiting_on_trainee,
            help="File slots trainees still need to prepare or replace.",
            border=True,
        )
        st.metric(
            "Open questions",
            open_questions,
            help="Trainee questions waiting for your answer.",
            border=True,
        )

    with st.container(border=True):
        done_ratio = (
            totals.approved_cases / totals.total_cases if totals.total_cases else 0.0
        )
        st.markdown("**Overall completion**")
        st.caption(
            f"{totals.approved_cases} of {totals.total_cases} cases approved "
            f"across {totals.trainees} trainees."
        )
        st.progress(done_ratio)

    render_trainer_question_inbox(repository)

    attention = [
        row
        for row in rows
        if int(row.get("waiting_on_trainer", 0))
        or int(row.get("waiting_on_trainee", 0))
        or int(row.get("overdue_cases", 0))
    ]
    st.subheader("Needs attention")
    if not attention:
        st.success("Nothing waiting right now.")
    else:
        for row in sorted(
            attention,
            key=lambda item: (
                -int(item.get("waiting_on_trainer", 0)),
                -int(item.get("overdue_cases", 0)),
                -int(item.get("waiting_on_trainee", 0)),
            ),
        ):
            with st.container(border=True):
                left, right = st.columns([3, 1], vertical_alignment="center")
                left.markdown(
                    f"**{row['full_name']}**  \n"
                    f"{waiting_label(row)}"
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

    frame = pd.DataFrame(rows)
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
                    "full_name",
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
                    "full_name": "Trainee",
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
        repository.create_trainee(
            full_name=full_name.strip(),
            email=email.strip() or None,
            start_date=start_date,
            timezone=timezone,
            created_by=user_id,
        )
    except APIError as exc:
        st.error(f"Could not create trainee: {exc.message}")
        return

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
            title=f"Set {case_row['set_no']} · Case {case_row['case_no']}",
            instructions=notes,
            schedule_due_date=schedule_due,
            due_date=due_date,
        )
    except APIError as exc:
        st.error(f"Could not assign case: {exc.message}")
        return

    st.success(f"Set {case_row['set_no']} · Case {case_row['case_no']} assigned.")
    st.rerun()


def render_cases(repository: TrainingRepository, user_id: str) -> None:
    del user_id
    render_page_header(
        "Cases",
        "Assign homework from the inbox. Open Review only when a package is ready.",
    )
    trainees = repository.list_active_trainees()
    if not trainees:
        st.info("Add a trainee first.")
        return

    labels = {row["id"]: row["full_name"] for row in trainees}
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
        )
    if trainee_id != requested_trainee:
        set_query(trainee=trainee_id, case=None)
        st.rerun()

    cases = repository.list_cases(trainee_id, include_files=True)
    assignments = repository.list_homework_for_cases([row["id"] for row in cases])
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

    cases = repository.list_cases(trainee_id, include_files=True)
    case = next((row for row in cases if row["id"] == case_id), None)
    if case is None:
        st.error("This case is unavailable or the link is no longer valid.")
        if st.button("Back to cases", icon=":material/arrow_back:"):
            st.switch_page("app_pages/trainer_cases.py")
        return

    assignments = repository.list_homework_for_cases([case_id])
    selected = enrich_cases([case], assignments, role="trainer").iloc[0].to_dict()

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

    back, heading = st.columns([1, 5], vertical_alignment="center")
    with back:
        if st.button("Back", icon=":material/arrow_back:"):
            st.switch_page(
                "app_pages/trainer_cases.py",
                query_params={"trainee": trainee_id, "case": case_id},
            )
    with heading:
        render_page_header(
            "Review",
            "Inspect files, leave corrections, answer questions, then publish.",
        )

    render_case_summary(selected)
    files_tab, review_tab, questions_tab = st.tabs(
        [
            ":material/folder: Files",
            ":material/rate_review: Feedback",
            ":material/help: Questions",
        ]
    )
    with files_tab:
        render_trainer_case_review(repository, case=case)
    with review_tab:
        render_trainer_revisions(repository, user_id=user_id, case=case)
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
