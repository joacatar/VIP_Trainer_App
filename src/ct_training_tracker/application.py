import streamlit as st

from ct_training_tracker.auth import clear_session
from ct_training_tracker.runtime import create_client_or_none, load_profile
from ct_training_tracker.views.login import render_login


def _render_sign_out(client) -> None:
    with st.sidebar:
        if st.button("Sign out"):
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

    st.sidebar.write(f"Signed in as **{profile['full_name'] or profile['role']}**")
    _render_sign_out(client)

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
                url_path="trainer/cases",
            ),
            st.Page(
                "app_pages/trainer_add_trainee.py",
                title="Add trainee",
                icon=":material/person_add:",
                url_path="trainer/trainees",
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
            )
        ]

    page = st.navigation(pages, position="top")
    page.run()
