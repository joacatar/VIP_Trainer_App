from dataclasses import dataclass

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError


@dataclass(frozen=True)
class SupabaseSettings:
    url: str
    publishable_key: str


def load_settings() -> SupabaseSettings | None:
    try:
        url = st.secrets.get("SUPABASE_URL", "")
        publishable_key = st.secrets.get("SUPABASE_PUBLISHABLE_KEY", "")
    except StreamlitSecretNotFoundError:
        return None
    if not url or not publishable_key:
        return None
    return SupabaseSettings(url=url, publishable_key=publishable_key)
