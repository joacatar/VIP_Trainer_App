from collections.abc import MutableMapping
from typing import Any

import streamlit as st

from ct_training_tracker.auth import store_login
from ct_training_tracker.components.ui import render_page_header
from supabase import Client


def render_login(client: Client, session: MutableMapping[str, Any]) -> None:
    left, content, right = st.columns([1, 1.2, 1])
    with content:
        render_page_header(
            "CT training tracker",
            "Manage CT disposition and planning training in one place.",
        )
        with st.container(border=True):
            st.subheader("Sign in")
            st.caption("Use the account provided by your training administrator.")
            with st.form("login", border=False):
                email = st.text_input(
                    "Email address",
                    autocomplete="email",
                    placeholder="name@example.com",
                )
                password = st.text_input(
                    "Password",
                    type="password",
                    autocomplete="current-password",
                )
                submitted = st.form_submit_button(
                    "Sign in",
                    type="primary",
                    width="stretch",
                    icon=":material/login:",
                )

    if not submitted:
        return

    if not email.strip() or not password:
        st.error("Enter your email address and password to sign in.")
        return

    try:
        logged_in = store_login(client, session, email.strip(), password)
    except Exception:
        st.error("We could not sign you in. Check your details and try again.")
        return

    if not logged_in:
        st.error("Sign-in did not return a valid session.")
        return
    st.rerun()
