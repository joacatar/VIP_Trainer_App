"""URL helpers for shareable trainer / trainee / case links."""

from __future__ import annotations

import streamlit as st


def query_value(name: str) -> str | None:
    value = st.query_params.get(name)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def set_query(
    *,
    trainee: str | None = None,
    case: str | None = None,
    view: str | None = None,
) -> None:
    """Replace trainee/case/view query params used by the case board."""
    current_trainee = query_value("trainee")
    current_case = query_value("case")
    current_view = query_value("view")
    next_trainee = trainee
    next_case = case
    # Preserve view unless the caller explicitly changes it.
    next_view = current_view if view is None else view

    if (
        next_trainee == current_trainee
        and next_case == current_case
        and next_view == current_view
    ):
        return

    params: dict[str, str] = {}
    if next_trainee:
        params["trainee"] = next_trainee
    if next_case:
        params["case"] = next_case
    if next_view:
        params["view"] = next_view
    st.query_params.clear()
    st.query_params.update(params)
