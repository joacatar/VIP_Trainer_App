import pandas as pd
import streamlit as st

from ct_training_tracker.models import Profile
from ct_training_tracker.repository import TrainingRepository


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
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
