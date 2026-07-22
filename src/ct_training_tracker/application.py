import streamlit as st

from ct_training_tracker.auth import clear_session
from ct_training_tracker.runtime import create_client_or_none, load_profile
from ct_training_tracker.views.login import render_login


def _render_account_panel(client, profile: dict) -> None:
    with st.sidebar:
        st.subheader(profile["full_name"] or "Training account")
        st.badge(profile["role"].replace("_", " ").title(), color="blue")
        st.caption("Signed in")
        st.space("small")
        if st.button(
            "Sign out",
            icon=":material/logout:",
            width="stretch",
        ):
            client.auth.sign_out()
            clear_session(st.session_state)
            st.rerun()


def run() -> None:
    client = create_client_or_none()
    if client is None:
        return

    if "access_token" not in st.session_state:
        page = st.navigation(
            [
                st.Page(
                    "app_pages/login.py",
                    title="Sign in",
                    icon=":material/login:",
                    url_path="login",
                    default=True,
                )
            ],
            position="hidden",
        )
        page.run()
        return

    profile = load_profile(client)
    if not profile:
        clear_session(st.session_state)
        st.error("No profile exists for this account.")
        render_login(client, st.session_state)
        return

    _render_account_panel(client, profile)

    if profile["role"] == "trainer":
        pages = [
            st.Page(
                "app_pages/trainer_dashboard.py",
                title="Dashboard",
                icon=":material/dashboard:",
                url_path="trainer",
                default=True,
            ),
            st.Page(
                "app_pages/trainer_cases.py",
                title="Cases",
                icon=":material/folder_open:",
                url_path="trainer-cases",
            ),
            st.Page(
                "app_pages/trainer_case_workspace.py",
                title="Review",
                icon=":material/rate_review:",
                url_path="trainer-case",
            ),
            st.Page(
                "app_pages/trainer_add_trainee.py",
                title="Add trainee",
                icon=":material/person_add:",
                url_path="trainer-trainees",
            ),
        ]
    else:
        pages = [
            st.Page(
                "app_pages/trainee_cases.py",
                title="My cases",
                icon=":material/assignment:",
                url_path="trainee",
                default=True,
            ),
            st.Page(
                "app_pages/trainee_case_workspace.py",
                title="Case workspace",
                icon=":material/open_in_new:",
                url_path="trainee-case",
            ),
        ]

    page = st.navigation(pages, position="top")
    page.run()
