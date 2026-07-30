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


# A single script run can call create_client_or_none()/load_profile() more
# than once (application.run() bootstraps, then each page's require_runtime()
# bootstraps again). Cache the pair per access token in session_state so
# every call after the first one in a session reuses it instead of hitting
# Supabase Auth (set_session/get_user) and the profiles table again.
RUNTIME_CACHE_KEY = "_app_runtime_cache"


def create_client_or_none() -> Client | None:
    settings = _load_settings()
    if settings is None:
        render_missing_configuration()
        return None

    access_token = st.session_state.get("access_token")
    if access_token:
        cached = st.session_state.get(RUNTIME_CACHE_KEY)
        if cached is not None and cached[0] == access_token:
            return cached[1]

    return create_authenticated_client(settings, st.session_state)


def load_profile(client: Client) -> Profile | None:
    access_token = st.session_state.get("access_token")
    if access_token:
        cached = st.session_state.get(RUNTIME_CACHE_KEY)
        if cached is not None and cached[0] == access_token and cached[1] is client:
            return cached[2]

    try:
        user_response = client.auth.get_user()
        user_id = user_response.user.id if user_response.user else None
        if not user_id:
            return None
        profile = TrainingRepository(client).get_profile(user_id)
    except Exception as exc:
        clear_session(st.session_state)
        st.error(f"Could not load your profile: {exc}")
        return None

    if profile is not None:
        access_token = st.session_state.get("access_token")
        if access_token:
            st.session_state[RUNTIME_CACHE_KEY] = (access_token, client, profile)
    return profile


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
