"""Rule-based per-case resource suggestions.

Data-only module: no Streamlit, no Supabase. Edit RESOURCE_RULES to change
what gets attached to new trainees' cases. Each rule has a `match` (empty =
all cases; supports set_no, case_no_range, section) and a `resource`
(resource_type file/link/note, title, and url or body).
"""

from __future__ import annotations

from typing import Any

RESOURCE_RULES: tuple[dict[str, Any], ...] = (
    {
        "match": {},
        "resource": {
            "resource_type": "note",
            "title": "Before you submit",
            "body": "Review the section checklist before submitting.",
        },
    },
    {
        "match": {"set_no": 1, "case_no_range": (1, 4)},
        "resource": {
            "resource_type": "link",
            "title": "Getting started guide",
            # Placeholder URL — replace with the real guide.
            "url": "https://example.com/vip-getting-started",
        },
    },
    {
        "match": {"case_no_range": (12, 13)},
        "resource": {
            "resource_type": "note",
            "title": "Manual planning reminder",
            # Placeholder copy — replace with real instructions.
            "body": "These cases are planned manually. Double-check landmarks "
            "before submitting.",
        },
    },
)


def _matches(case: dict[str, Any], match: dict[str, Any]) -> bool:
    set_no = match.get("set_no")
    if set_no is not None and int(case.get("set_no") or 0) != int(set_no):
        return False
    case_no_range = match.get("case_no_range")
    if case_no_range is not None:
        low, high = case_no_range
        case_no = int(case.get("case_no") or 0)
        if not (int(low) <= case_no <= int(high)):
            return False
    section = match.get("section")
    if section is not None and case.get("section") != section:
        return False
    return True


def suggest_resources_for_case(case: dict[str, Any]) -> list[dict[str, Any]]:
    """Suggested resource dicts for one case, in rule order."""
    suggestions: list[dict[str, Any]] = []
    for sort_order, rule in enumerate(RESOURCE_RULES):
        if _matches(case, rule["match"]):
            suggestions.append({**rule["resource"], "sort_order": sort_order})
    return suggestions


def build_system_resources(
    cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Rows ready for bulk insert, marked created_by='system'."""
    rows: list[dict[str, Any]] = []
    for case in cases:
        for suggestion in suggest_resources_for_case(case):
            rows.append(
                {
                    "case_id": case["id"],
                    "created_by": "system",
                    **suggestion,
                }
            )
    return rows
