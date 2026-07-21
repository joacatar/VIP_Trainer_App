import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from ct_training_tracker.auth import clear_session, create_authenticated_client
from ct_training_tracker.config import settings_from_mapping
from ct_training_tracker.repository import TrainingRepository
from ct_training_tracker.views.login import render_login
from ct_training_tracker.views.trainee import render_trainee_portal
from ct_training_tracker.views.trainer import render_trainer_portal


def _load_settings():
    try:
        return settings_from_mapping(st.secrets)
    except StreamlitSecretNotFoundError:
        return None


def _render_missing_configuration() -> None:
    st.error("Supabase is not configured.")
    st.code(
        'SUPABASE_URL = "https://your-project.supabase.co"\n'
        'SUPABASE_PUBLISHABLE_KEY = "your-publishable-key"',
        language="toml",
    )
    st.caption("Add these values to .streamlit/secrets.toml.")


def run() -> None:
    settings = _load_settings()
    if settings is None:
        _render_missing_configuration()
        return

    client = create_authenticated_client(settings, st.session_state)
    if "access_token" not in st.session_state:
        render_login(client, st.session_state)
        return

    try:
        user_response = client.auth.get_user()
        user_id = user_response.user.id if user_response.user else None
        profile = TrainingRepository(client).get_profile(user_id) if user_id else None
    except Exception as exc:
        clear_session(st.session_state)
        st.error(f"Could not load your profile: {exc}")
        return

    if not profile:
        clear_session(st.session_state)
        st.error("No profile exists for this account.")
        return

    if st.sidebar.button("Sign out"):
        client.auth.sign_out()
        clear_session(st.session_state)
        st.rerun()

    repository = TrainingRepository(client)
    if profile["role"] == "trainer":
        render_trainer_portal(repository, profile)
    else:
        render_trainee_portal(repository, profile)
