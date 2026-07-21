import pandas as pd
import streamlit as st

from ct_training_tracker.models import Profile
from ct_training_tracker.repository import TrainingRepository


def _file_progress(requirements: object) -> str:
    if not isinstance(requirements, list):
        return "0 / 3 accepted"
    accepted = sum(
        requirement.get("status") == "accepted"
        for requirement in requirements
        if isinstance(requirement, dict)
    )
    return f"{accepted} / 3 accepted"


def _render_case_set(frame: pd.DataFrame, set_no: int) -> None:
    set_frame = frame.loc[frame["set_no"] == set_no].copy()
    set_frame["status"] = set_frame["status"].str.replace("_", " ").str.title()
    set_frame["files"] = set_frame["file_requirements"].apply(_file_progress)
    visible_columns = [
        "case_no",
        "status",
        "due_date",
        "estimated_completion_date",
        "files",
    ]
    st.dataframe(
        set_frame[visible_columns].rename(
            columns={
                "case_no": "Case",
                "status": "Status",
                "due_date": "Due date",
                "estimated_completion_date": "Estimated completion",
                "files": "Files",
            }
        ),
        hide_index=True,
        use_container_width=True,
    )


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

    rows = repository.list_cases(trainee["id"], include_files=True)
    current_phase = trainee["current_phase"].replace("_", " ").title()
    st.caption(f"Current phase: {current_phase}")

    frame = pd.DataFrame(rows)
    set_one_tab, set_two_tab = st.tabs(["Set 1", "Set 2"])
    with set_one_tab:
        _render_case_set(frame, 1)
    with set_two_tab:
        _render_case_set(frame, 2)
