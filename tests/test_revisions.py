from ct_training_tracker.files import (
    screenshot_storage_path,
    validate_screenshot,
)
from ct_training_tracker.revisions import (
    REVIEW_SECTIONS,
    can_start_revision,
    count_open_corrections_in_tree,
    open_corrections,
    section_label,
)


def test_review_sections_are_eight_fixed_keys() -> None:
    assert len(REVIEW_SECTIONS) == 8
    assert REVIEW_SECTIONS[0][0] == "scan"
    assert REVIEW_SECTIONS[-1][0] == "glenoid_implant"
    assert section_label("glenoid_landmark") == "Glenoid landmark"


def test_section_checklists_cover_all_review_sections() -> None:
    from ct_training_tracker.revisions import SECTION_CHECKLISTS, checklist_for_section

    keys = {key for key, _, _ in REVIEW_SECTIONS}
    assert set(SECTION_CHECKLISTS) == keys
    assert len(checklist_for_section("scan")) == 2
    assert "Sample input" not in checklist_for_section("humeral_implant")
    assert "Meets Expectation" not in " ".join(checklist_for_section("scan"))
    assert len(checklist_for_section("scapula")) == len(
        set(checklist_for_section("scapula"))
    )


def test_feedback_bodies_from_checklist_and_free_text() -> None:
    from ct_training_tracker.revisions import feedback_bodies

    assert feedback_bodies(
        ["Minor movement to glenoid center", "  "],
        "  Extra note  ",
    ) == [
        "Minor movement to glenoid center",
        "Extra note",
    ]
    assert feedback_bodies([], "") == []
    assert feedback_bodies([], "Only free text") == ["Only free text"]


def test_partition_sections_empty_means_ok() -> None:
    from ct_training_tracker.revisions import partition_sections_by_feedback

    revision = {
        "revision_sections": [
            {"section_key": "scan", "corrections": []},
            {
                "section_key": "scapula",
                "corrections": [{"body": "Minor movement to glenoid center"}],
            },
            {"section_key": "rider_form", "corrections": []},
        ]
    }
    needs, ok = partition_sections_by_feedback(revision)
    assert [row["section_key"] for row in needs] == ["scapula"]
    assert [row["section_key"] for row in ok] == ["scan", "rider_form"]


def test_can_start_revision_only_in_review_or_corrections_sent() -> None:
    assert can_start_revision("in_review")
    assert can_start_revision("corrections_sent")
    assert not can_start_revision("assigned")
    assert not can_start_revision("submitted")


def test_open_corrections_filters_resolved() -> None:
    rows = [
        {"id": "1", "status": "open"},
        {"id": "2", "status": "resolved"},
        {"id": "3", "status": "open"},
    ]
    assert [row["id"] for row in open_corrections(rows)] == ["1", "3"]


def test_count_open_corrections_in_tree() -> None:
    revision = {
        "revision_sections": [
            {
                "corrections": [
                    {"status": "open"},
                    {"status": "resolved"},
                ]
            },
            {"corrections": [{"status": "open"}]},
        ]
    }
    assert count_open_corrections_in_tree(revision) == 2


def test_screenshot_path_uses_owner_case_and_correction() -> None:
    path = screenshot_storage_path(
        owner_user_id="trainee-user",
        case_id="case-1",
        correction_id="corr-1",
        filename="Shot One.PNG",
    )
    assert path == "trainee-user/case-1/screenshots/corr-1/Shot_One.PNG"
    assert validate_screenshot("note.webp") == "note.webp"
