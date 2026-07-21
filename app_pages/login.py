"""Sign-in page."""

import streamlit as st

from ct_training_tracker.runtime import create_client_or_none
from ct_training_tracker.views.login import render_login


def main() -> None:
    client = create_client_or_none()
    if client is None:
        return
    render_login(client, st.session_state)


main()
