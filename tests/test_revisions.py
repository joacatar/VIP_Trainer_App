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
