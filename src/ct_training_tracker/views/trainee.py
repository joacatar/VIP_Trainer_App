import streamlit as st

from ct_training_tracker.components.ui import (
    render_empty_state,
    render_page_header,
)
from ct_training_tracker.metrics import count_file_waiting, count_tasks
from ct_training_tracker.models import Profile
from ct_training_tracker.repository import TrainingRepository
from ct_training_tracker.routing import query_value
from ct_training_tracker.views.case_board import (
    enrich_cases,
    pick_next_case,
    render_case_summary,
    render_next_case_card,
    select_case_from_list,
)
from ct_training_tracker.views.case_files import render_trainee_case_uploads
from ct_training_tracker.views.questions import render_trainee_questions
from ct_training_tracker.views.revisions import render_trainee_revisions


def render_trainee_portal(
    repository: TrainingRepository,
    profile: Profile,
) -> None:
    render_page_header(
        f"Welcome, {profile['full_name'] or 'Trainee'}",
        "Open the next case that needs you, or browse the list to switch.",
    )
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
    st.caption(
        f"{current_phase} · {tasks.open_tasks} open · "
        f"{tasks.with_trainer} with trainer · {tasks.approved} approved"
    )

    assignments = repository.list_homework_for_cases([row["id"] for row in cases])
    frame = enrich_cases(cases, assignments, role="trainee")
    render_next_case_card(
        pick_next_case(frame, role="trainee"),
        key_prefix="trainee",
        trainee_id=trainee["id"],
    )

    list_col, preview_col = st.columns([1.05, 1.2], gap="large")
    with list_col:
        st.subheader("Case inbox")
        selected = select_case_from_list(
            frame,
            key_prefix="trainee",
            role="trainee",
            trainee_id=trainee["id"],
            default_filter="needs_you",
        )
    with preview_col:
        st.subheader("Quick view")
        if selected is None:
            render_empty_state(
                "Select a case from the inbox",
                detail=(
                    "Open the workspace when you are ready to work on "
                    "files or questions."
                ),
            )
            return

        render_case_summary(selected)
        if st.button(
            "Open case workspace",
            key=f"open_workspace_{selected['id']}",
            type="primary",
            width="content",
            icon=":material/open_in_new:",
        ):
            st.switch_page(
                "app_pages/trainee_case_workspace.py",
                query_params={"case": selected["id"]},
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

    cases = repository.list_cases(trainee["id"], include_files=True)
    case = next((row for row in cases if row["id"] == case_id), None)
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
    file_counts = count_file_waiting([case])
    files_tab, review_tab, questions_tab = st.tabs(
        [
            ":material/folder: Files",
            ":material/rate_review: Feedback",
            ":material/help: Questions",
        ]
    )
    with files_tab:
        st.caption(
            f"Package {file_counts.sent} ready · {file_counts.to_send} to send · "
            f"{file_counts.accepted} accepted"
        )
        trainer_name = repository.get_trainer_display_name_for_trainee(trainee["id"])
        render_trainee_case_uploads(
            repository,
            user_id=profile["id"],
            case=case,
            trainer_name=trainer_name,
        )
    with review_tab:
        render_trainee_revisions(repository, case=case)
    with questions_tab:
        render_trainee_questions(repository, user_id=profile["id"], case=case)
