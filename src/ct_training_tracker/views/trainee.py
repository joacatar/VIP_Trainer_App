import streamlit as st

from ct_training_tracker.metrics import count_file_waiting, count_tasks
from ct_training_tracker.models import Profile
from ct_training_tracker.repository import TrainingRepository
from ct_training_tracker.views.case_board import (
    enrich_cases,
    render_case_summary,
    select_case_from_list,
)
from ct_training_tracker.views.case_files import render_trainee_case_uploads
from ct_training_tracker.views.revisions import render_trainee_revisions


def render_trainee_portal(
    repository: TrainingRepository,
    profile: Profile,
) -> None:
    st.header(f"Welcome, {profile['full_name'] or 'Trainee'}")
    st.caption("Path: `/trainee?case=…`")
    trainee = repository.get_trainee_for_user(profile["id"])
    if not trainee:
        st.warning(
            "Your account has not been linked to a trainee record yet. "
            "Ask your trainer to finish the setup."
        )
        return

    cases = repository.list_cases(trainee["id"], include_files=True)
    current_phase = trainee["current_phase"].replace("_", " ").title()
    tasks = count_tasks(cases)
    st.caption(f"Current phase: {current_phase}")

    st.markdown("##### Tasks")
    task_cols = st.columns(3)
    task_cols[0].metric(
        "Open tasks",
        tasks.open_tasks,
        help="Assigned cases where you still need to act.",
    )
    task_cols[1].metric(
        "With trainer",
        tasks.with_trainer,
        help="Packages submitted for review (trainer is working on them).",
    )
    task_cols[2].metric(
        "Approved",
        tasks.approved,
        help="Cases the trainer has fully approved.",
    )

    assignments = repository.list_homework_for_cases([row["id"] for row in cases])
    frame = enrich_cases(cases, assignments)
    cases_by_id = {row["id"]: row for row in cases}

    list_col, detail_col = st.columns([0.95, 1.35], gap="large")
    with list_col:
        st.markdown("#### Case list")
        selected = select_case_from_list(
            frame,
            key_prefix="trainee",
            trainee_id=trainee["id"],
        )

    with detail_col:
        st.markdown("#### Case detail")
        if selected is None:
            st.info("Select a case on the left.")
            return

        render_case_summary(selected)
        case = cases_by_id[selected["id"]]
        file_counts = count_file_waiting([case])

        files_tab, review_tab = st.tabs(
            [
                ":material/folder: Files",
                ":material/rate_review: Feedback",
            ]
        )
        with files_tab:
            st.caption(
                "Paste OneDrive links, mark ready, then notify the trainer."
            )
            file_cols = st.columns(3)
            file_cols[0].metric("To send", file_counts.to_send)
            file_cols[1].metric("Ready", file_counts.sent)
            file_cols[2].metric("Accepted", file_counts.accepted)

            trainer_name = repository.get_trainer_display_name_for_trainee(
                trainee["id"]
            )
            render_trainee_case_uploads(
                repository,
                user_id=profile["id"],
                case=case,
                trainer_name=trainer_name,
            )
        with review_tab:
            render_trainee_revisions(repository, case=case)
