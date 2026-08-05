"""Trainee progress journey — 32 case nodes across Set 1 / Set 2."""

from __future__ import annotations

from typing import Any, Literal

import streamlit as st

from ct_training_tracker.metrics import AttentionState, case_attention_state

JourneyTone = Literal["not_started", "needs_you", "with_trainer", "approved"]

_TONE_COLORS: dict[JourneyTone, str] = {
    "not_started": "#64748b",
    "needs_you": "#fb923c",
    "with_trainer": "#38bdf8",
    "approved": "#4ade80",
}


def journey_tone_for_attention(state: AttentionState) -> JourneyTone:
    if state == "approved":
        return "approved"
    if state == "needs_trainer":
        return "with_trainer"
    if state == "with_trainee":
        return "needs_you"
    return "not_started"


def _node_svg(number: int, tone: JourneyTone, *, filled: bool) -> str:
    color = _TONE_COLORS[tone]
    fill = color if filled else "transparent"
    text = "#0f172a" if filled and tone == "approved" else "#e2e8f0"
    return (
        f'<span class="ct-journey-node" title="Case {number}" '
        f'style="border-color:{color};background:{fill};color:{text}">'
        f"{number}</span>"
    )


def _connector(prev_approved: bool) -> str:
    color = _TONE_COLORS["approved"] if prev_approved else "#334155"
    return (
        f'<span class="ct-journey-line" style="background:{color}"></span>'
    )


def render_progress_journey(
    cases: list[dict[str, Any]],
    *,
    today,
    threads_by_case: dict[str, list[dict[str, Any]]] | None = None,
) -> None:
    """Two rows of 16 connected nodes colored by case_attention_state."""
    threads_by_case = threads_by_case or {}
    by_set: dict[int, dict[int, dict[str, Any]]] = {1: {}, 2: {}}
    for case in cases:
        set_no = int(case.get("set_no") or 0)
        case_no = int(case.get("case_no") or 0)
        if set_no in by_set and 1 <= case_no <= 16:
            by_set[set_no][case_no] = case

    st.markdown(
        """
<style>
.ct-journey-row {
  display: flex;
  align-items: center;
  gap: 0;
  margin: 0.35rem 0 0.7rem;
  overflow-x: auto;
  padding-bottom: 0.15rem;
}
.ct-journey-label {
  width: 3.2rem;
  flex: 0 0 3.2rem;
  font-size: 0.78rem;
  color: #94a3b8;
  font-weight: 600;
}
.ct-journey-node {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.55rem;
  height: 1.55rem;
  border-radius: 999px;
  border: 2px solid;
  font-size: 0.62rem;
  font-weight: 700;
  flex: 0 0 auto;
}
.ct-journey-line {
  height: 2px;
  width: 0.55rem;
  flex: 1 1 0.55rem;
  min-width: 0.35rem;
  max-width: 0.85rem;
  opacity: 0.9;
}
.ct-journey-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.85rem;
  margin-top: 0.35rem;
  font-size: 0.78rem;
  color: #94a3b8;
}
.ct-journey-legend i {
  display: inline-block;
  width: 0.7rem;
  height: 0.7rem;
  border-radius: 999px;
  border: 2px solid;
  margin-right: 0.3rem;
  vertical-align: -0.1rem;
}
</style>
        """,
        unsafe_allow_html=True,
    )

    for set_no in (1, 2):
        parts = [
            '<div class="ct-journey-row">'
            f'<span class="ct-journey-label">Set {set_no}</span>'
        ]
        prev_approved = False
        for case_no in range(1, 17):
            case = by_set[set_no].get(case_no)
            if case is None:
                tone: JourneyTone = "not_started"
            else:
                attention = case_attention_state(
                    case,
                    [],
                    threads_by_case.get(str(case.get("id") or ""), []),
                    [],
                    today,
                )
                tone = journey_tone_for_attention(attention.state)
            if case_no > 1:
                parts.append(_connector(prev_approved))
            filled = tone == "approved"
            parts.append(_node_svg(case_no, tone, filled=filled))
            prev_approved = tone == "approved"
        parts.append("</div>")
        st.markdown("".join(parts), unsafe_allow_html=True)

    legend_bits: list[str] = []
    for tone, label in (
        ("not_started", "Not started"),
        ("needs_you", "Needs you"),
        ("with_trainer", "With trainer"),
        ("approved", "Approved"),
    ):
        fill = (
            "transparent"
            if tone != "approved"
            else _TONE_COLORS[tone]
        )
        legend_bits.append(
            f'<span><i style="border-color:{_TONE_COLORS[tone]};'
            f'background:{fill}"></i>{label}</span>'
        )
    st.markdown(
        f'<div class="ct-journey-legend">{"".join(legend_bits)}</div>',
        unsafe_allow_html=True,
    )
