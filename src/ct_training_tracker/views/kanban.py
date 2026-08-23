"""Trainer kanban board — scan all cases by attention lane."""

from __future__ import annotations

import datetime as dt
from typing import Any

import streamlit as st

from ct_training_tracker.data_cache import cached_trainee_cases
from ct_training_tracker.metrics import (
    APPROVED_VISIBLE,
    BOARD_LANES,
    AttentionState,
    BoardCard,
    build_board_card,
    group_board_cards,
)
from ct_training_tracker.repository import TrainingRepository
from ct_training_tracker.trainee_filters import trainee_display_name
from ct_training_tracker.views.bulk_due_dates import (
    is_select_mode,
    selected_case_ids,
    toggle_case_selected,
)


def _open_questions_by_case(
    repository: TrainingRepository,
) -> dict[str, list[dict[str, Any]]]:
    rows = repository.list_questions_for_trainer(status="open")
    by_case: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        case_id = str(row.get("case_id") or "")
        if case_id:
            by_case.setdefault(case_id, []).append(row)
    return by_case


def collect_board_cards(
    repository: TrainingRepository,
    trainees: list[dict[str, Any]],
    *,
    today: dt.date | None = None,
) -> list[BoardCard]:
    """Build cards for every case across the given trainees."""
    today = today or dt.date.today()
    questions_by_case = _open_questions_by_case(repository)
    cards: list[BoardCard] = []
    for trainee in trainees:
        trainee_id = str(trainee["id"])
        name = trainee_display_name(trainee)
        for case in cached_trainee_cases(repository, trainee_id, include_files=False):
            case = {**case, "trainee_id": case.get("trainee_id") or trainee_id}
            cards.append(
                build_board_card(
                    case,
                    trainee_name=name,
                    today=today,
                    open_questions=questions_by_case.get(str(case["id"]), []),
                )
            )
    return cards


def render_case_board(
    repository: TrainingRepository,
    trainees: list[dict[str, Any]],
    *,
    trainee_filter_id: str | None = None,
) -> None:
    """Four-lane board. Cards open Review (or Cases inbox for unassigned)."""
    pool = trainees
    if trainee_filter_id:
        pool = [row for row in trainees if str(row["id"]) == trainee_filter_id]
    cards = collect_board_cards(repository, pool)
    lanes = group_board_cards(cards)

    columns = st.columns(4, gap="small")
    for column, (state, title) in zip(columns, BOARD_LANES, strict=True):
        with column:
            _render_lane(state, title, lanes[state])


def _render_lane(
    state: AttentionState,
    title: str,
    cards: list[BoardCard],
) -> None:
    accent = state == "needs_trainer"
    count = len(cards)
    if accent:
        st.markdown(f"**{title}** · :blue-badge[{count}]")
    else:
        st.markdown(f"**{title}** · :gray[{count}]")

    visible = cards
    overflow = 0
    if state == "approved" and len(cards) > APPROVED_VISIBLE:
        visible = cards[:APPROVED_VISIBLE]
        overflow = len(cards) - APPROVED_VISIBLE

    if not cards:
        st.caption("—")
        return

    for card in visible:
        _render_card(card, dimmed=state == "approved")

    if overflow:
        st.caption(f"+{overflow} more")


def _render_card(card: BoardCard, *, dimmed: bool) -> None:
    with st.container(border=True):
        if is_select_mode():
            checked = st.checkbox(
                "Select",
                value=card.case_id in selected_case_ids(),
                key=f"board_select_{card.case_id}",
                label_visibility="collapsed",
            )
            toggle_case_selected(card.case_id, selected=checked)

        title_row = st.columns([3, 1], vertical_alignment="center")
        with title_row[0]:
            if dimmed:
                st.markdown(f":material/check_circle: **{card.case_label}**")
            else:
                st.markdown(f"**{card.case_label}**")
        with title_row[1]:
            if card.badge_label and card.badge_color:
                st.badge(card.badge_label, color=card.badge_color)  # type: ignore[arg-type]

        scope = "Live case" if card.phase_no == 2 else f"Set {card.set_no}"
        st.caption(f"{card.trainee_name} · {scope}")

        if card.footer:
            if card.footer_urgent:
                st.markdown(f":red[{card.footer}]")
            elif card.open_question_count and "question" in card.footer:
                st.caption(f":material/chat_bubble: {card.footer}")
            elif card.state == "with_trainee":
                st.caption(f":material/sync: {card.footer}")
            else:
                st.caption(f":material/calendar_today: {card.footer}")

        if is_select_mode():
            return

        if st.button(
            "Open",
            key=f"board_open_{card.case_id}",
            width="stretch",
            type="primary" if card.state == "needs_trainer" else "secondary",
        ):
            # Unassigned cases stay in the Inbox so homework can be set.
            # Everything else opens Review (history for approved, work for the rest).
            if card.needs_assignment:
                st.switch_page(
                    "app_pages/trainer_cases.py",
                    query_params={
                        "trainee": card.trainee_id,
                        "case": card.case_id,
                        "view": "inbox",
                    },
                )
            else:
                st.switch_page(
                    "app_pages/trainer_case_workspace.py",
                    query_params={
                        "trainee": card.trainee_id,
                        "case": card.case_id,
                    },
                )
