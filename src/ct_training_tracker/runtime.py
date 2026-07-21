"""Shared authenticated runtime for multipage views."""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from ct_training_tracker.auth import clear_session, create_authenticated_client
from ct_training_tracker.config import settings_from_mapping
from ct_training_tracker.models import Profile
from ct_training_tracker.repository import TrainingRepository
from supabase import Client


@dataclass(frozen=True)
class AppRuntime:
    client: Client
    repository: TrainingRepository
    profile: Profile


def _load_settings():
    try:
        return settings_from_mapping(st.secrets)
    except StreamlitSecretNotFoundError:
        return None


def render_missing_configuration() -> None:
    st.error("Supabase is not configured.")
    st.code(
        'SUPABASE_URL = "https://your-project.supabase.co"\n'
        'SUPABASE_PUBLISHABLE_KEY = "your-publishable-key"',
        language="toml",
    )
    st.caption("Add these values to .streamlit/secrets.toml.")


def create_client_or_none() -> Client | None:
    settings = _load_settings()
    if settings is None:
        render_missing_configuration()
        return None
    return create_authenticated_client(settings, st.session_state)


def load_profile(client: Client) -> Profile | None:
    try:
        user_response = client.auth.get_user()
        user_id = user_response.user.id if user_response.user else None
        if not user_id:
            return None
        return TrainingRepository(client).get_profile(user_id)
    except Exception as exc:
        clear_session(st.session_state)
        st.error(f"Could not load your profile: {exc}")
        return None


def require_runtime() -> AppRuntime | None:
    """Return runtime for authenticated pages, or stop the page early."""
    client = create_client_or_none()
    if client is None:
        return None
    if "access_token" not in st.session_state:
        st.warning("Sign in to continue.")
        return None

    profile = load_profile(client)
    if not profile:
        clear_session(st.session_state)
        st.error("No profile exists for this account.")
        return None

    return AppRuntime(
        client=client,
        repository=TrainingRepository(client),
        profile=profile,
    )
