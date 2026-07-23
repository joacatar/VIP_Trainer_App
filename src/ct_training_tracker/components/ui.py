"""Shared native Streamlit presentation primitives."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Literal

import streamlit as st

from ct_training_tracker.case_labels import case_title

StatusColor = Literal[
    "red", "orange", "yellow", "blue", "green", "violet", "gray", "grey", "primary"
]


_STATUS_COLORS: dict[str, StatusColor] = {
    "approved": "green",
    "accepted": "green",
    "assigned": "orange",
    "submitted": "blue",
    "in_review": "blue",
    "under_review": "blue",
    "awaiting_resubmission": "orange",
    "replacement_requested": "orange",
    "corrections_sent": "orange",
    "not_started": "gray",
}


def status_color(raw_status: str) -> StatusColor:
    return _STATUS_COLORS.get(raw_status, "gray")


def render_page_header(title: str, description: str | None = None) -> None:
    """Render a consistent user-facing page title and short orientation text."""
    st.title(title)
    if description:
        st.caption(description)


@contextmanager
def constrained_width(width: int = 640) -> Iterator[None]:
    """Center a readable content column for forms and short workflows."""
    with st.container(horizontal=True, horizontal_alignment="center"):
        with st.container(width=width):
            yield


def render_empty_state(
    message: str,
    *,
    detail: str | None = None,
    icon: str = ":material/inbox:",
) -> None:
    """Calm neutral placeholder when the user has not chosen work yet."""
    with st.container(border=True):
        st.markdown(f"{icon}  \n**{message}**")
        if detail:
            st.caption(detail)


def render_case_header(
    case: dict[str, Any],
    *,
    bordered: bool = True,
) -> None:
    """Render the shared case context before role-specific work areas."""
    status = str(case.get("raw_status") or case.get("status") or "not_started")
    status_label = str(case.get("status") or status.replace("_", " ").title())
    next_action = case.get("next_step")

    def _body() -> None:
        st.subheader(case_title(case))
        summary, status_column = st.columns([2, 1], vertical_alignment="center")
        with summary:
            due_date = case.get("due_date") or "—"
            order = case.get("order_number")
            order_bit = f"Order {order} · " if order else ""
            st.caption(
                f"{order_bit}Due {due_date} · "
                f"{case.get('files') or 'No file status yet'}"
            )
            if next_action:
                st.markdown(f"**Next:** {next_action}")
        with status_column:
            st.badge(status_label, color=status_color(status))
        if case.get("notes"):
            st.info(case["notes"], icon=":material/notes:")

    if bordered:
        with st.container(border=True):
            _body()
    else:
        _body()
