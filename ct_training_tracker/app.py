import datetime as dt
from typing import Any

import pandas as pd
import streamlit as st
from postgrest.exceptions import APIError
from supabase import Client, create_client

from config import SupabaseSettings, load_settings


st.set_page_config(
    page_title="CT Initial Training Tracker",
    page_icon="🫁",
    layout="wide",
)


def make_client(settings: SupabaseSettings) -> Client:
    client = create_client(settings.url, settings.publishable_key)
    access_token = st.session_state.get("access_token")
    refresh_token = st.session_state.get("refresh_token")
    if access_token and refresh_token:
        try:
            response = client.auth.set_session(access_token, refresh_token)
            if response.session:
                st.session_state.access_token = response.session.access_token
                st.session_state.refresh_token = response.session.refresh_token
        except Exception:
            clear_session()
    return client


def clear_session() -> None:
    for key in ("access_token", "refresh_token", "user_id", "profile"):
        st.session_state.pop(key, None)


def login(client: Client) -> None:
    st.title("CT Initial Training Tracker")
    st.caption("CT disposition and CT planning")

    with st.form("login"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary")

    if not submitted:
        return

    try:
        response = client.auth.sign_in_with_password(
            {"email": email.strip(), "password": password}
        )
    except Exception as exc:
        st.error(f"Sign-in failed: {exc}")
        return

    if not response.session or not response.user:
        st.error("Sign-in did not return a valid session.")
        return

    st.session_state.access_token = response.session.access_token
    st.session_state.refresh_token = response.session.refresh_token
    st.session_state.user_id = response.user.id
    st.rerun()


def load_profile(client: Client) -> dict[str, Any] | None:
    user = client.auth.get_user()
    if not user or not user.user:
        return None

    result = (
        client.table("profiles")
        .select("id, role, full_name")
        .eq("id", user.user.id)
        .single()
        .execute()
    )
    return result.data


def trainer_dashboard(client: Client) -> None:
    st.header("Training overview")
    result = (
        client.table("trainee_progress")
        .select(
            "trainee_id, full_name, current_phase, total_cases, approved_cases, "
            "overdue_cases, total_files, accepted_files, estimated_completion_date"
        )
        .execute()
    )
    rows = result.data or []

    if not rows:
        st.info("No trainees yet. Add the first trainee to generate their 32 cases.")
        return

    frame = pd.DataFrame(rows)
    total_cases = int(frame["total_cases"].sum())
    approved_cases = int(frame["approved_cases"].sum())
    overdue_cases = int(frame["overdue_cases"].sum())
    accepted_files = int(frame["accepted_files"].sum())
    total_files = int(frame["total_files"].sum())

    columns = st.columns(4)
    columns[0].metric("Case progress", f"{approved_cases}/{total_cases}")
    columns[1].metric("Files accepted", f"{accepted_files}/{total_files}")
    columns[2].metric("Overdue cases", overdue_cases)
    columns[3].metric("Active trainees", len(frame))

    frame["case_progress"] = (
        frame["approved_cases"].astype(str) + " / " + frame["total_cases"].astype(str)
    )
    frame["file_progress"] = (
        frame["accepted_files"].astype(str) + " / " + frame["total_files"].astype(str)
    )
    st.dataframe(
        frame[
            [
                "full_name",
                "current_phase",
                "case_progress",
                "file_progress",
                "overdue_cases",
                "estimated_completion_date",
            ]
        ],
        hide_index=True,
        use_container_width=True,
    )


def add_trainee_form(client: Client, user_id: str) -> None:
    st.subheader("Add trainee")
    with st.form("add_trainee", clear_on_submit=True):
        left, middle, right = st.columns(3)
        full_name = left.text_input("Full name")
        email = middle.text_input("Email")
        start_date = right.date_input("Training start date", value=dt.date.today())
        timezone = st.selectbox(
            "Timezone",
            ["Australia/Sydney", "America/New_York"],
        )
        submitted = st.form_submit_button("Create trainee", type="primary")

    if not submitted:
        return
    if not full_name.strip():
        st.error("Full name is required.")
        return

    try:
        client.table("trainees").insert(
            {
                "full_name": full_name.strip(),
                "email": email.strip() or None,
                "start_date": start_date.isoformat(),
                "timezone": timezone,
                "created_by": user_id,
            }
        ).execute()
    except APIError as exc:
        st.error(f"Could not create trainee: {exc.message}")
        return

    st.success("Trainee created with 32 scheduled cases and 96 file requirements.")
    st.rerun()


def trainer_cases(client: Client) -> None:
    st.header("Cases")
    trainees = (
        client.table("trainees")
        .select("id, full_name, start_date, current_phase")
        .eq("active", True)
        .order("full_name")
        .execute()
        .data
        or []
    )
    if not trainees:
        st.info("Add a trainee first.")
        return

    labels = {row["id"]: row["full_name"] for row in trainees}
    trainee_id = st.selectbox(
        "Trainee",
        options=list(labels),
        format_func=lambda value: labels[value],
    )
    rows = (
        client.table("cases")
        .select(
            "id, set_no, case_no, phase, status, schedule_due_date, due_date, "
            "estimated_completion_date"
        )
        .eq("trainee_id", trainee_id)
        .order("set_no")
        .order("case_no")
        .execute()
        .data
        or []
    )
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def trainer_portal(client: Client, profile: dict[str, Any]) -> None:
    st.sidebar.write(f"Signed in as **{profile['full_name'] or 'Trainer'}**")
    page = st.sidebar.radio("Navigation", ["Dashboard", "Trainees", "Cases"])
    if page == "Dashboard":
        trainer_dashboard(client)
    elif page == "Trainees":
        st.header("Trainees")
        add_trainee_form(client, profile["id"])
    else:
        trainer_cases(client)


def trainee_portal(client: Client, profile: dict[str, Any]) -> None:
    st.header(f"Welcome, {profile['full_name'] or 'Trainee'}")
    trainee = (
        client.table("trainees")
        .select("id, full_name, current_phase, start_date")
        .eq("auth_user_id", profile["id"])
        .maybe_single()
        .execute()
        .data
    )
    if not trainee:
        st.warning(
            "Your account has not been linked to a trainee record yet. "
            "Ask your trainer to finish the setup."
        )
        return

    rows = (
        client.table("cases")
        .select(
            "id, set_no, case_no, status, due_date, estimated_completion_date, "
            "file_requirements(kind, status)"
        )
        .eq("trainee_id", trainee["id"])
        .order("set_no")
        .order("case_no")
        .execute()
        .data
        or []
    )
    st.caption(f"Current phase: {trainee['current_phase'].replace('_', ' ').title()}")
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def main() -> None:
    settings = load_settings()
    if settings is None:
        st.error("Supabase is not configured.")
        st.code(
            'SUPABASE_URL = "https://your-project.supabase.co"\n'
            'SUPABASE_PUBLISHABLE_KEY = "your-publishable-key"',
            language="toml",
        )
        st.caption("Add these values to .streamlit/secrets.toml.")
        return

    client = make_client(settings)
    if "access_token" not in st.session_state:
        login(client)
        return

    try:
        profile = load_profile(client)
    except Exception as exc:
        clear_session()
        st.error(f"Could not load your profile: {exc}")
        return

    if not profile:
        clear_session()
        st.error("No profile exists for this account.")
        return

    if st.sidebar.button("Sign out"):
        client.auth.sign_out()
        clear_session()
        st.rerun()

    if profile["role"] == "trainer":
        trainer_portal(client, profile)
    else:
        trainee_portal(client, profile)


if __name__ == "__main__":
    main()
