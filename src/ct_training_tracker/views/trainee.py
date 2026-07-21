import streamlit as st

from ct_training_tracker.models import Profile
from ct_training_tracker.repository import TrainingRepository
from ct_training_tracker.views.case_board import (
    enrich_cases,
    render_case_summary,
    select_case_from_list,
)
from ct_training_tracker.views.case_files import render_trainee_case_uploads


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
    st.caption(f"Current phase: {current_phase}")

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
        st.markdown("##### Files")
        render_trainee_case_uploads(
            repository,
            user_id=profile["id"],
            case=cases_by_id[selected["id"]],
        )
