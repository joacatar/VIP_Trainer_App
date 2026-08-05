"""Trainee progress journey — CCv2 path matching the mockup (circles + chips)."""

from __future__ import annotations

from html import escape
from typing import Any, Literal

import streamlit as st

from ct_training_tracker.case_labels import case_title
from ct_training_tracker.metrics import AttentionState, case_attention_state

JourneyTone = Literal["not_started", "needs_you", "with_trainer", "approved"]

# Fallback when journey_category is missing from a case row (pre-migration).
JOURNEY_CATEGORY_BY_CASE_NO: dict[int, str] = {
    **{n: "Success Journey" for n in range(1, 5)},
    **{n: "OV Adjusted" for n in range(5, 7)},
    **{n: "Rejections" for n in range(7, 12)},
    **{n: "Manual" for n in range(12, 15)},
    15: "Duplicate",
    16: "Axial3D Case",
}

_CHIP_DISPLAY: dict[str, str] = {
    "Success Journey": "Success journey",
    "OV Adjusted": "OV adjusted",
    "Rejections": "Rejections",
    "Manual": "Manual",
    "Duplicate": "Duplicate",
    "Axial3D Case": "Axial3D case",
}

_TONE_COLORS: dict[JourneyTone, str] = {
    "not_started": "#64748b",
    "needs_you": "#fb923c",
    "with_trainer": "#38bdf8",
    "approved": "#4ade80",
}

_WORKSPACE_PAGE = "app_pages/trainee_case_workspace.py"

_HTML = """
<div class="ct-j" id="ct-journey-root"></div>
"""

_CSS = """
.ct-j {
  font-family: inherit;
  color: #e2e8f0;
  width: 100%;
}
.ct-j-set {
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 0.75rem;
  padding: 0.9rem 1rem 0.75rem;
  margin-bottom: 0.75rem;
  background: rgba(15, 23, 42, 0.35);
}
.ct-j-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: #f8fafc;
  margin: 0 0 0.75rem;
}
.ct-j-flow {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.45rem 0.3rem;
  row-gap: 0.65rem;
}
.ct-j-chip {
  display: inline-flex;
  align-items: center;
  height: 28px;
  padding: 0 0.7rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: rgba(51, 65, 85, 0.55);
  color: #cbd5e1;
  font-size: 0.72rem;
  font-weight: 500;
  letter-spacing: 0.01em;
  white-space: nowrap;
  line-height: 1;
}
.ct-j-conn {
  width: 14px;
  height: 2px;
  background: #475569;
  border-radius: 1px;
  flex: 0 0 14px;
}
.ct-j-node {
  box-sizing: border-box;
  width: 34px;
  height: 34px;
  min-width: 34px;
  border-radius: 999px;
  border: 2px solid #64748b;
  background: transparent;
  color: #94a3b8;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.85rem;
  font-weight: 600;
  line-height: 1;
  cursor: pointer;
  padding: 0;
  margin: 0;
  text-decoration: none;
  font-family: inherit;
  transition: transform 0.12s ease, box-shadow 0.12s ease;
}
.ct-j-node:hover:not(:disabled) {
  transform: scale(1.06);
}
.ct-j-node:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.ct-j-node.tone-not_started {
  border-color: #64748b;
  color: #94a3b8;
  background: transparent;
}
.ct-j-node.tone-needs_you {
  border-color: #fb923c;
  color: #fb923c;
  background: transparent;
}
.ct-j-node.tone-with_trainer {
  border-color: #38bdf8;
  color: #7dd3fc;
  background: rgba(56, 189, 248, 0.12);
}
.ct-j-node.tone-approved {
  border-color: #4ade80;
  color: #0f172a;
  background: #4ade80;
}
.ct-j-node.is-next {
  width: 40px;
  height: 40px;
  min-width: 40px;
  font-size: 0.95rem;
  box-shadow: 0 0 0 0 rgba(251, 146, 60, 0.55);
  animation: ct-j-pulse 1.8s ease-out infinite;
}
@keyframes ct-j-pulse {
  0% { box-shadow: 0 0 0 0 rgba(251, 146, 60, 0.55); }
  70% { box-shadow: 0 0 0 10px rgba(251, 146, 60, 0); }
  100% { box-shadow: 0 0 0 0 rgba(251, 146, 60, 0); }
}
.ct-j-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.85rem;
  margin-top: 0.15rem;
  font-size: 0.78rem;
  color: #94a3b8;
}
.ct-j-legend span {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}
.ct-j-legend i {
  display: inline-block;
  width: 0.7rem;
  height: 0.7rem;
  border-radius: 999px;
  border: 2px solid;
  box-sizing: border-box;
}
"""

_JS = """
export default function (component) {
  const { data, parentElement, setTriggerValue } = component
  const root =
    parentElement.querySelector("#ct-journey-root") ||
    parentElement.querySelector(".ct-j")
  if (!root) return

  const sets = Array.isArray(data?.sets) ? data.sets : []
  const legend = Array.isArray(data?.legend) ? data.legend : []

  function chipHtml(label) {
    return `<span class="ct-j-chip">${label}</span>`
  }

  function nodeHtml(item) {
    const classes = [
      "ct-j-node",
      `tone-${item.tone || "not_started"}`,
      item.is_next ? "is-next" : "",
    ]
      .filter(Boolean)
      .join(" ")
    const title = item.title ? ` title="${item.title}"` : ""
    if (!item.case_id) {
      return (
        `<button type="button" class="${classes}" disabled` +
        `${title}>${item.label}</button>`
      )
    }
    return (
      `<button type="button" class="${classes}" ` +
      `data-case-id="${item.case_id}"` +
      `${title}>${item.label}</button>`
    )
  }

  function flowHtml(items) {
    return items
      .map((item) => {
        if (item.kind === "chip") return chipHtml(item.label)
        if (item.kind === "conn") {
          return '<span class="ct-j-conn" aria-hidden="true"></span>'
        }
        return nodeHtml(item)
      })
      .join("")
  }

  const legendHtml = legend.length
    ? `<div class="ct-j-legend">${legend
        .map((row) => {
          const style =
            `border-color:${row.color};background:${row.fill}`
          return (
            `<span><i style="${style}"></i>${row.label}</span>`
          )
        })
        .join("")}</div>`
    : ""

  root.innerHTML =
    sets
      .map(
        (set) =>
          `<section class="ct-j-set">` +
          `<div class="ct-j-title">${set.title || ""}</div>` +
          `<div class="ct-j-flow">${flowHtml(set.items || [])}</div>` +
          `</section>`
      )
      .join("") + legendHtml

  root.querySelectorAll("button[data-case-id]").forEach((btn) => {
    btn.onclick = (event) => {
      event.preventDefault()
      const caseId = btn.getAttribute("data-case-id")
      if (caseId) setTriggerValue("selected_case", caseId)
    }
  })
}
"""

_JOURNEY = st.components.v2.component(
    "ct_progress_journey",
    html=_HTML,
    css=_CSS,
    js=_JS,
)


def journey_category_for_case(case: dict[str, Any]) -> str:
    raw = case.get("journey_category")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    case_no = int(case.get("case_no") or 0)
    return JOURNEY_CATEGORY_BY_CASE_NO.get(case_no, "Success Journey")


def journey_tone_for_attention(state: AttentionState) -> JourneyTone:
    if state == "approved":
        return "approved"
    if state == "needs_trainer":
        return "with_trainer"
    if state == "with_trainee":
        return "needs_you"
    return "not_started"


def _chip_label(category: str) -> str:
    return _CHIP_DISPLAY.get(category, category)


def build_journey_items(
    nodes: dict[int, dict[str, Any]],
    *,
    today,
    threads_by_case: dict[str, list[dict[str, Any]]],
    next_up_case_id: str | None,
) -> list[dict[str, Any]]:
    """Pure builder for one set's flow items (chip / conn / node)."""
    items: list[dict[str, Any]] = []
    previous_category: str | None = None
    previous_was_node = False

    for case_no in range(1, 17):
        case = nodes.get(case_no)
        category = (
            journey_category_for_case(case)
            if case is not None
            else JOURNEY_CATEGORY_BY_CASE_NO.get(case_no, "Success Journey")
        )
        if category != previous_category:
            items.append(
                {
                    "kind": "chip",
                    "label": escape(_chip_label(category)),
                }
            )
            previous_category = category
            previous_was_node = False

        if previous_was_node:
            items.append({"kind": "conn"})

        if case is None:
            items.append(
                {
                    "kind": "node",
                    "label": str(case_no),
                    "tone": "not_started",
                    "case_id": None,
                    "title": "",
                    "is_next": False,
                }
            )
            previous_was_node = True
            continue

        attention = case_attention_state(
            case,
            [],
            threads_by_case.get(str(case.get("id") or ""), []),
            [],
            today,
        )
        tone = journey_tone_for_attention(attention.state)
        case_id = str(case["id"])
        items.append(
            {
                "kind": "node",
                "label": str(case_no),
                "tone": tone,
                "case_id": case_id,
                "title": escape(f"Open {case_title(case)}"),
                "is_next": bool(
                    next_up_case_id and case_id == str(next_up_case_id)
                ),
            }
        )
        previous_was_node = True

    return items


def render_progress_journey(
    cases: list[dict[str, Any]],
    *,
    today,
    threads_by_case: dict[str, list[dict[str, Any]]] | None = None,
    next_up_case_id: str | None = None,
) -> None:
    """One continuous flex-wrapping path per set; chips mark category changes."""
    threads_by_case = threads_by_case or {}
    by_set: dict[int, dict[int, dict[str, Any]]] = {1: {}, 2: {}}
    for case in cases:
        set_no = int(case.get("set_no") or 0)
        case_no = int(case.get("case_no") or 0)
        if set_no in by_set and 1 <= case_no <= 16:
            by_set[set_no][case_no] = case

    sets_payload = []
    for set_no in (1, 2):
        sets_payload.append(
            {
                "title": escape(f"Set {set_no} · your journey"),
                "items": build_journey_items(
                    by_set[set_no],
                    today=today,
                    threads_by_case=threads_by_case,
                    next_up_case_id=next_up_case_id,
                ),
            }
        )

    legend = []
    for tone, label in (
        ("not_started", "Not started"),
        ("needs_you", "Needs you"),
        ("with_trainer", "With trainer"),
        ("approved", "Approved"),
    ):
        legend.append(
            {
                "label": label,
                "color": _TONE_COLORS[tone],
                "fill": (
                    _TONE_COLORS[tone] if tone == "approved" else "transparent"
                ),
            }
        )

    result = _JOURNEY(
        data={"sets": sets_payload, "legend": legend},
        key="trainee_progress_journey",
        on_selected_case_change=lambda: None,
        width="stretch",
        height=320,
    )

    selected = getattr(result, "selected_case", None)
    if isinstance(selected, str) and selected:
        st.switch_page(
            _WORKSPACE_PAGE,
            query_params={"case": selected},
        )
