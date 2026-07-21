from collections.abc import MutableMapping
from typing import Any

import streamlit as st

from ct_training_tracker.auth import store_login
from supabase import Client


def render_login(client: Client, session: MutableMapping[str, Any]) -> None:
    st.title("CT Initial Training Tracker")
    st.caption("CT disposition and CT planning")

    with st.form("login"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary")

    if not submitted:
        return

    try:
        logged_in = store_login(client, session, email, password)
    except Exception as exc:
        st.error(f"Sign-in failed: {exc}")
        return

    if not logged_in:
        st.error("Sign-in did not return a valid session.")
        return
    st.rerun()
