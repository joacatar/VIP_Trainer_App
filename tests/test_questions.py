from ct_training_tracker.questions import (
    count_open_questions,
    count_unread_answers,
    is_unread_answer,
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


def test_is_unread_answer_requires_answered_status() -> None:
    assert not is_unread_answer({"status": "open"})
    assert not is_unread_answer({"status": "resolved", "answered_at": "2026-01-01"})


def test_is_unread_answer_true_when_never_viewed() -> None:
    question = {
        "status": "answered",
        "answered_at": "2026-01-02T00:00:00Z",
        "trainee_viewed_at": None,
    }
    assert is_unread_answer(question)


def test_is_unread_answer_false_when_viewed_after_answer() -> None:
    question = {
        "status": "answered",
        "answered_at": "2026-01-02T00:00:00Z",
        "trainee_viewed_at": "2026-01-03T00:00:00Z",
    }
    assert not is_unread_answer(question)


def test_is_unread_answer_true_when_re_answered_after_last_view() -> None:
    # Trainee viewed an earlier answer, then the trainer answered again.
    question = {
        "status": "answered",
        "answered_at": "2026-01-05T00:00:00Z",
        "trainee_viewed_at": "2026-01-03T00:00:00Z",
    }
    assert is_unread_answer(question)


def test_count_unread_answers() -> None:
    rows = [
        {
            "status": "answered",
            "answered_at": "2026-01-02T00:00:00Z",
            "trainee_viewed_at": None,
        },
        {
            "status": "answered",
            "answered_at": "2026-01-02T00:00:00Z",
            "trainee_viewed_at": "2026-01-03T00:00:00Z",
        },
        {"status": "open"},
        {"status": "resolved"},
    ]
    assert count_unread_answers(rows) == 1
