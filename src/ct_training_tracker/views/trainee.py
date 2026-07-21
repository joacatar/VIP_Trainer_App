import streamlit as st

from ct_training_tracker.models import Profile
from ct_training_tracker.repository import TrainingRepository
from ct_training_tracker.views.case_board import enrich_cases, visible_case_frame


def render_trainee_portal(
    repository: TrainingRepository,
    profile: Profile,
) -> None:
    st.header(f"Welcome, {profile['full_name'] or 'Trainee'}")
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

    set_one_tab, set_two_tab = st.tabs(["Set 1", "Set 2"])
    with set_one_tab:
        st.dataframe(
            visible_case_frame(frame, 1),
            hide_index=True,
            use_container_width=True,
        )
    with set_two_tab:
        st.dataframe(
            visible_case_frame(frame, 2),
            hide_index=True,
            use_container_width=True,
        )
