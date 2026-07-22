"""Fixed review sections, PR checklists, and revision helpers."""

from __future__ import annotations

from typing import Any

REVIEW_SECTIONS: tuple[tuple[str, str, int], ...] = (
    ("scan", "Scan", 1),
    ("rider_form", "Rider form", 2),
    ("segmentation", "Segmentation", 3),
    ("scapula", "Scapula", 4),
    ("glenoid_landmark", "Glenoid landmark", 5),
    ("humeral_landmark", "Humeral landmark", 6),
    ("humeral_implant", "Humeral implant", 7),
    ("glenoid_implant", "Glenoid implant", 8),
)

SECTION_LABELS = {key: label for key, label, _ in REVIEW_SECTIONS}
REVISION_START_STATUSES = {"in_review", "corrections_sent"}

# Peer-review checklist templates (from legacy page2.html; cleaned).
# Empty section = OK — lists are correction prompts only (no "meets expectation").
SECTION_CHECKLISTS: dict[str, tuple[str, ...]] = {
    "scan": (
        "Better scan choice available to have chosen",
        "Scan is a rejection and cannot be planned with",
    ),
    "rider_form": (
        "Rider form is missing a few fields of information or is not signed",
        "Rider form is missing a comment",
        "Rider form has extra comments",
    ),
    "segmentation": (
        "Soft tissue still remained around glenoid rim",
        "Soft tissue still remained on glenoid face",
        "Excessive soft tissue was around scapula",
        "Light humeral head remained on glenoid",
        "Major humeral head remained on glenoid",
        "Better thresholding choice was available",
        "Better cortex choice was available for choosing",
    ),
    "scapula": (
        "Minor movement to glenoid center",
        "Minor movement to trigonum scapula",
        "Minor movement to angulus inferior",
        "The angulus inferior needs to be on the cortex",
        "The angulus inferior needs to be centered in the last "
        "slice of the transverse view",
        "Glenoid Center only centered in one view",
        "Glenoid Center needs to be more superior",
        "Major movement to two or more landmarks",
        "SN should be on the neck",
    ),
    "glenoid_landmark": (
        "Minor movement of anterior or posterior glenoid rim landmark",
        "Minor movement of superior glenoid rim landmark",
        "Glenoid plane too expanded on glenoid",
        "Glenoid plane too cramped on glenoid",
        "Version should be updated to mimic native vault",
        "Major change to version",
        "Major change to inclination",
        "Reset glenoid plane landmarks to new locations",
        "Forgot to set some coracoid / acromion / scapular neck landmarks",
        "GRA and GRP are not in the same plane",
    ),
    "humeral_landmark": (
        "Minor correction to humeral shaft",
        "Major correction to humeral shaft",
        "Shaft landmarks should not be deep onto the axis canal, "
        "they should mimic the implant length",
        "Humeral plane directed more through humeral head or changed "
        "Neck Shaft Angle",
        "Slight change to other humeral landmarks",
        "Forgot to place one or more other humeral landmarks",
        "AN landmark should be on solid bone on the calcar area",
        "Humeral head size reduced or increased",
        "Humeral head size not centered",
    ),
    "humeral_implant": (
        "Humeral stem selection not appropriate for anatomy",
        "Cage Screw should be reduced until it is small; it has to have "
        "at least 8mm gap with the cortex",
        "Eclipse can be closer to the cortex to mimic the articulating "
        "surface better",
        "Cup head of stem should match glenosphere size",
    ),
    "glenoid_implant": (
        "Need to update implant due to changes in landmarks",
        "Rolled to better superior implant trajectory",
        "Implant version changed",
        "Implant inclination changed",
        "Implant positioning should be inferior and posterior avoiding "
        "unstable bone",
        "VL implant should be more centered into the glenoid anatomy; "
        "it should follow and sit onto the anatomy",
        "VL roll should change to mimic anatomy better",
        "Implant downsizing unnecessary",
        "Perforated a polyethylene component (VL)",
        "Medialized slightly too deep into glenoid",
        "Able to achieve 100% backside seating",
        "AP Measurement is missing for glenosphere size",
        "Glenosphere size is incorrect",
        "Glenosphere size is too small",
        "Glenosphere size is too large",
        "The usage of half augments is not permitted",
    ),
}


def section_label(section_key: str) -> str:
    return SECTION_LABELS.get(section_key, section_key.replace("_", " ").title())


def checklist_for_section(section_key: str) -> tuple[str, ...]:
    return SECTION_CHECKLISTS.get(section_key, ())


def can_start_revision(case_status: str) -> bool:
    return case_status in REVISION_START_STATUSES


def feedback_bodies(
    selected_items: list[str],
    free_text: str,
) -> list[str]:
    """Build one correction body per checklist item, plus optional free text."""
    bodies = [item.strip() for item in selected_items if item and item.strip()]
    cleaned = free_text.strip()
    if cleaned:
        bodies.append(cleaned)
    return bodies


def section_has_corrections(section: dict[str, Any]) -> bool:
    corrections = section.get("corrections") or []
    return any(isinstance(row, dict) and row.get("body") for row in corrections)


def partition_sections_by_feedback(
    revision: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (sections_needing_corrections, sections_ok)."""
    needs: list[dict[str, Any]] = []
    ok: list[dict[str, Any]] = []
    for section in revision.get("revision_sections") or []:
        if not isinstance(section, dict):
            continue
        if section_has_corrections(section):
            needs.append(section)
        else:
            ok.append(section)
    return needs, ok


def open_corrections(corrections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in corrections if row.get("status") == "open"]


def count_open_corrections_in_tree(revision: dict[str, Any]) -> int:
    total = 0
    for section in revision.get("revision_sections") or []:
        if not isinstance(section, dict):
            continue
        for correction in section.get("corrections") or []:
            if isinstance(correction, dict) and correction.get("status") == "open":
                total += 1
    return total
