"""Trainee questions inbox at /trainee-questions."""

import streamlit as st

from ct_training_tracker.runtime import require_runtime
from ct_training_tracker.views.questions import render_trainee_question_inbox


def main() -> None:
    runtime = require_runtime()
    if runtime is None:
        return
    if runtime.profile["role"] != "trainee":
        return

    trainee = runtime.repository.get_trainee_for_user(runtime.profile["id"])
    if not trainee:
        st.warning(
            "Your account has not been linked to a trainee record yet. "
            "Ask your trainer to finish the setup."
        )
        return

    cases = runtime.repository.list_cases(trainee["id"], released_only=True)
    render_trainee_question_inbox(
        runtime.repository,
        user_id=runtime.profile["id"],
        trainee=trainee,
        cases=cases,
    )


main()
