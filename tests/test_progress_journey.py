"""Unit tests for Feature 8.2 journey category helpers."""

from __future__ import annotations

import datetime as dt

from ct_training_tracker.components.progress_journey import (
    JOURNEY_CATEGORY_BY_CASE_NO,
    build_journey_items,
    journey_category_for_case,
    journey_tone_for_attention,
)


def test_journey_category_uses_column_when_present() -> None:
    assert (
        journey_category_for_case(
            {"case_no": 7, "journey_category": "Rejections"}
        )
        == "Rejections"
    )


def test_journey_category_falls_back_by_case_no() -> None:
    assert journey_category_for_case({"case_no": 1}) == "Success Journey"
    assert journey_category_for_case({"case_no": 5}) == "OV Adjusted"
    assert journey_category_for_case({"case_no": 11}) == "Rejections"
    assert journey_category_for_case({"case_no": 14}) == "Manual"
    assert journey_category_for_case({"case_no": 15}) == "Duplicate"
    assert journey_category_for_case({"case_no": 16}) == "Axial3D Case"


def test_journey_category_map_covers_all_sixteen() -> None:
    assert sorted(JOURNEY_CATEGORY_BY_CASE_NO) == list(range(1, 17))
    # Rejections must span the typical wrap boundary (7–11).
    for case_no in range(7, 12):
        assert JOURNEY_CATEGORY_BY_CASE_NO[case_no] == "Rejections"


def test_journey_tone_mapping() -> None:
    assert journey_tone_for_attention("approved") == "approved"
    assert journey_tone_for_attention("needs_trainer") == "with_trainer"
    assert journey_tone_for_attention("with_trainee") == "needs_you"
    assert journey_tone_for_attention("assigned") == "not_started"


def test_build_journey_items_inline_chips_and_connectors() -> None:
    nodes = {
        case_no: {
            "id": f"c{case_no}",
            "set_no": 1,
            "case_no": case_no,
            "catalog_label": f"{case_no}A",
            "status": "not_started",
            "journey_category": JOURNEY_CATEGORY_BY_CASE_NO[case_no],
        }
        for case_no in range(1, 17)
    }
    items = build_journey_items(
        nodes,
        today=dt.date(2026, 8, 5),
        threads_by_case={},
        next_up_case_id="c3",
    )
    kinds = [item["kind"] for item in items]
    assert kinds[0] == "chip"
    assert items[0]["label"] == "Success journey"
    # chip, node, conn, node... then chip at OV adjusted (case 5)
    assert "chip" in kinds
    assert kinds.count("chip") == 6
    nodes_only = [item for item in items if item["kind"] == "node"]
    assert len(nodes_only) == 16
    assert nodes_only[2]["is_next"] is True
    # No connector immediately after a chip
    for index, item in enumerate(items[:-1]):
        if item["kind"] == "chip":
            assert items[index + 1]["kind"] != "conn"
