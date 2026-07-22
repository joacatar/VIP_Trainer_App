from ct_training_tracker.questions import (
    count_open_questions,
    question_section_label,
    section_options,
)


def test_question_section_label_defaults_to_general() -> None:
    assert question_section_label(None) == "General"
    assert question_section_label("scan") == "Scan"


def test_section_options_include_general_and_eight_sections() -> None:
    options = section_options()
    assert options[0] == (None, "General (whole case)")
    assert len(options) == 9


def test_count_open_questions() -> None:
    rows = [
        {"status": "open"},
        {"status": "answered"},
        {"status": "open"},
        {"status": "resolved"},
    ]
    assert count_open_questions(rows) == 2
