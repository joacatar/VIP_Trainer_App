from collections.abc import MutableMapping
from typing import Any

from supabase import Client, create_client

from ct_training_tracker.config import SupabaseSettings

SESSION_KEYS = ("access_token", "refresh_token", "user_id")


def clear_session(session: MutableMapping[str, Any]) -> None:
    for key in SESSION_KEYS:
        session.pop(key, None)


def create_authenticated_client(
    settings: SupabaseSettings,
    session: MutableMapping[str, Any],
) -> Client:
    client = create_client(settings.url, settings.publishable_key)
    access_token = session.get("access_token")
    refresh_token = session.get("refresh_token")
    if not access_token or not refresh_token:
        return client

    try:
        response = client.auth.set_session(access_token, refresh_token)
    except Exception:
        clear_session(session)
        return client

    if response.session:
        session["access_token"] = response.session.access_token
        session["refresh_token"] = response.session.refresh_token
    return client


def store_login(
    client: Client,
    session: MutableMapping[str, Any],
    email: str,
    password: str,
) -> bool:
    response = client.auth.sign_in_with_password(
        {"email": email.strip(), "password": password}
    )
    if not response.session or not response.user:
        return False

    session["access_token"] = response.session.access_token
    session["refresh_token"] = response.session.refresh_token
    session["user_id"] = response.user.id
    return True
