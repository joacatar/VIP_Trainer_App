"""Helpers for hiding practice / test trainee records from trainer views."""

from __future__ import annotations

from typing import Any

import streamlit as st

SHOW_TEST_TRAINEES_KEY = "show_test_trainees"


def show_test_trainees() -> bool:
    return bool(st.session_state.get(SHOW_TEST_TRAINEES_KEY, False))


def is_test_trainee(row: dict[str, Any]) -> bool:
    return bool(row.get("is_test") or row.get("trainee_is_test"))


def filter_trainees(
    rows: list[dict[str, Any]],
    *,
    include_test: bool | None = None,
) -> list[dict[str, Any]]:
    include = show_test_trainees() if include_test is None else include_test
    if include:
        return list(rows)
    return [row for row in rows if not is_test_trainee(row)]


def trainee_display_name(row: dict[str, Any]) -> str:
    name = str(row.get("full_name") or "Trainee")
    return f"{name} · Test" if is_test_trainee(row) else name
