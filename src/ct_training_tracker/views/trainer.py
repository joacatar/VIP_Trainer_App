import datetime as dt

import pandas as pd
import streamlit as st
from postgrest.exceptions import APIError

from ct_training_tracker.metrics import summarize_progress
from ct_training_tracker.models import Profile
from ct_training_tracker.repository import TrainingRepository
from ct_training_tracker.routing import query_value, set_query
from ct_training_tracker.views.case_board import (
    enrich_cases,
    render_case_summary,
    select_case_from_list,
)
from ct_training_tracker.views.case_files import render_trainer_case_review


def render_dashboard(repository: TrainingRepository) -> None:
    st.header("Training overview")
    st.caption("Path: `/trainer`")
    rows = repository.list_progress()
    if not rows:
        st.info("No trainees yet. Add the first trainee to generate their 32 cases.")
        return

    totals = summarize_progress(rows)
    columns = st.columns(4)
    columns[0].metric(
        "Case progress",
        f"{totals.approved_cases}/{totals.total_cases}",
    )
    columns[1].metric(
        "Files accepted",
        f"{totals.accepted_files}/{totals.total_files}",
    )
    columns[2].metric("Overdue cases", totals.overdue_cases)
    columns[3].metric("Active trainees", totals.trainees)

    frame = pd.DataFrame(rows)
    frame["case_progress"] = (
        frame["approved_cases"].astype(str) + " / " + frame["total_cases"].astype(str)
    )
    frame["file_progress"] = (
        frame["accepted_files"].astype(str) + " / " + frame["total_files"].astype(str)
    )
    st.dataframe(
        frame[
            [
                "full_name",
                "current_phase",
                "case_progress",
                "file_progress",
                "overdue_cases",
                "estimated_completion_date",
            ]
        ],
        hide_index=True,
        use_container_width=True,
    )


def render_trainees(repository: TrainingRepository, user_id: str) -> None:
    st.header("Add trainee")
    st.caption("Path: `/trainer/trainees`")
    with st.form("add_trainee", clear_on_submit=True):
        left, middle, right = st.columns(3)
        full_name = left.text_input("Full name")
        email = middle.text_input("Email")
        start_date = right.date_input("Training start date", value=dt.date.today())
        timezone = st.selectbox(
            "Timezone",
            ["Australia/Sydney", "America/New_York"],
        )
        submitted = st.form_submit_button("Create trainee", type="primary")

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


def _assign_case(repository: TrainingRepository, *, case_row: dict) -> None:
    if case_row["raw_status"] != "not_started":
        return

    schedule_due = dt.date.fromisoformat(str(case_row["schedule_due_date"]))
    with st.form(f"assign_case_{case_row['id']}"):
        due_date = st.date_input(
            "Due date",
            value=schedule_due,
            help="Suggested from the training schedule.",
        )
        notes = st.text_area(
            "Notes for trainee (optional)",
            placeholder="Anything they should focus on for this case.",
        )
        submitted = st.form_submit_button("Assign case", type="primary")

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


def render_cases(repository: TrainingRepository) -> None:
    st.header("Cases")
    st.caption("Path: `/trainer/cases?trainee=…&case=…`")
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
    frame = enrich_cases(cases, assignments)
    cases_by_id = {row["id"]: row for row in cases}

    list_col, detail_col = st.columns([0.95, 1.35], gap="large")
    with list_col:
        st.markdown("#### Case list")
        selected = select_case_from_list(
            frame,
            key_prefix="trainer",
            trainee_id=trainee_id,
        )

    with detail_col:
        st.markdown("#### Case detail")
        if selected is None:
            st.info("Select a case on the left.")
            return

        render_case_summary(selected)
        if selected["raw_status"] == "not_started":
            st.markdown("##### Assign")
            _assign_case(repository, case_row=selected)
        else:
            st.markdown("##### Files")
            render_trainer_case_review(
                repository,
                case=cases_by_id[selected["id"]],
            )


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
        render_cases(repository)
    else:
        render_trainees(repository, profile["id"])
