import datetime as dt

from ct_training_tracker.metrics import (
    FileWaitingCounts,
    ProgressTotals,
    TaskCounts,
    board_card_badge,
    build_board_card,
    case_attention_state,
    count_file_waiting,
    count_tasks,
    first_pass_sections,
    group_board_cards,
    open_thread_count_by_section,
    summarize_progress,
    threads_persisting_n_revisions,
    trainer_case_bucket,
    waiting_label,
)

TODAY = dt.date(2026, 8, 4)


def _attention(case, revisions=(), threads=(), questions=(), today=TODAY):
    return case_attention_state(
        case, list(revisions), list(threads), list(questions), today
    )


def test_attention_unassigned_case_is_assigned_and_needs_assignment() -> None:
    attention = _attention({"status": "not_started"})
    assert attention.state == "assigned"
    assert attention.needs_assignment is True


def test_attention_no_submissions_yet_is_assigned() -> None:
    attention = _attention({"status": "assigned"})
    assert attention.state == "assigned"
    assert attention.needs_assignment is False
    assert attention.overdue is False


def test_attention_package_in_review_needs_trainer() -> None:
    assert _attention({"status": "in_review"}).state == "needs_trainer"


def test_attention_revision_sent_back_is_with_trainee() -> None:
    revisions = [{"status": "published"}]
    attention = _attention({"status": "corrections_sent"}, revisions)
    assert attention.state == "with_trainee"


def test_attention_resolved_threads_but_unpublished_review_needs_trainer() -> None:
    revisions = [{"status": "published"}, {"status": "draft"}]
    threads = [{"status": "resolved"}, {"status": "resolved"}]
    attention = _attention({"status": "corrections_sent"}, revisions, threads)
    assert attention.state == "needs_trainer"


def test_attention_open_question_sets_flag_without_changing_state() -> None:
    questions = [{"status": "open"}, {"status": "resolved"}]
    attention = _attention({"status": "assigned"}, questions=questions)
    assert attention.state == "assigned"
    assert attention.has_open_question is True


def test_attention_overdue_and_in_review() -> None:
    case = {"status": "in_review", "due_date": "2026-08-01"}
    attention = _attention(case)
    assert attention.state == "needs_trainer"
    assert attention.overdue is True


def test_attention_approved_never_overdue() -> None:
    case = {"status": "approved", "due_date": "2026-08-01"}
    attention = _attention(case)
    assert attention.state == "approved"
    assert attention.overdue is False


def test_attention_new_revision_after_approval_request_needs_trainer() -> None:
    revisions = [{"status": "published"}, {"status": "published"}]
    attention = _attention({"status": "in_review"}, revisions)
    assert attention.state == "needs_trainer"


def test_attention_awaiting_resubmission_is_with_trainee() -> None:
    assert _attention({"status": "awaiting_resubmission"}).state == "with_trainee"


def test_trainer_case_bucket_matches_attention_states() -> None:
    assert trainer_case_bucket("not_started") == "needs_you"
    assert trainer_case_bucket("in_review") == "needs_you"
    assert trainer_case_bucket("corrections_sent") == "with_other"
    assert trainer_case_bucket("assigned") == "with_other"
    assert trainer_case_bucket("approved") == "approved"


def test_board_card_badge_priority_overdue_then_due_today_then_question() -> None:
    overdue = _attention({"status": "in_review", "due_date": "2026-08-01"})
    assert board_card_badge(
        overdue, due_date="2026-08-01", has_open_question=True, today=TODAY
    ) == ("Overdue", "red")

    due_today = _attention({"status": "in_review", "due_date": "2026-08-04"})
    assert board_card_badge(
        due_today, due_date="2026-08-04", has_open_question=True, today=TODAY
    ) == ("Due today", "orange")

    question = _attention({"status": "in_review", "due_date": "2026-08-10"})
    assert board_card_badge(
        question, due_date="2026-08-10", has_open_question=True, today=TODAY
    ) == ("Question", "orange")

    approved = _attention({"status": "approved", "due_date": "2026-08-01"})
    assert (
        board_card_badge(
            approved, due_date="2026-08-01", has_open_question=True, today=TODAY
        )
        is None
    )


def test_build_board_card_and_group_lanes() -> None:
    cards = [
        build_board_card(
            {
                "id": "c1",
                "trainee_id": "t1",
                "status": "in_review",
                "due_date": "2026-08-01",
                "set_no": 1,
                "case_no": 13,
                "catalog_label": "13A",
            },
            trainee_name="Aaron Fong",
            today=TODAY,
        ),
        build_board_card(
            {
                "id": "c2",
                "trainee_id": "t1",
                "status": "corrections_sent",
                "due_date": "2026-08-10",
                "set_no": 1,
                "case_no": 12,
                "catalog_label": "12A",
            },
            trainee_name="Aaron Fong",
            today=TODAY,
            revisions=[{"status": "published", "published_at": "2026-08-03T12:00:00Z"}],
        ),
        build_board_card(
            {
                "id": "c3",
                "trainee_id": "t2",
                "status": "assigned",
                "due_date": "2026-08-12",
                "set_no": 1,
                "case_no": 16,
                "catalog_label": "16A",
            },
            trainee_name="Max Pentecost",
            today=TODAY,
        ),
        build_board_card(
            {
                "id": "c4",
                "trainee_id": "t1",
                "status": "approved",
                "set_no": 1,
                "case_no": 1,
                "catalog_label": "1A",
            },
            trainee_name="Aaron Fong",
            today=TODAY,
        ),
    ]
    # Pad approved so overflow logic stays testable at the UI layer.
    for index in range(5):
        cards.append(
            build_board_card(
                {
                    "id": f"approved-{index}",
                    "trainee_id": "t1",
                    "status": "approved",
                    "set_no": 1,
                    "case_no": index + 2,
                    "catalog_label": f"{index + 2}A",
                },
                trainee_name="Aaron Fong",
                today=TODAY,
            )
        )

    lanes = group_board_cards(cards)
    assert [c.case_label for c in lanes["needs_trainer"]] == ["Case 13A"]
    assert lanes["needs_trainer"][0].badge_label == "Overdue"
    assert lanes["needs_trainer"][0].footer_urgent is True
    assert lanes["with_trainee"][0].footer == "Revision sent Aug 3"
    assert lanes["assigned"][0].case_label == "Case 16A"
    assert len(lanes["approved"]) == 6


def test_open_thread_count_by_section_counts_only_open_threads() -> None:
    threads = [
        {"id": "t1", "section": "scan", "status": "open"},
        {"id": "t2", "section": "scan", "status": "open"},
        {"id": "t3", "section": "scan", "status": "resolved"},
        {"id": "t4", "section": "rider_form", "status": "open"},
    ]

    assert open_thread_count_by_section(threads) == {"scan": 2, "rider_form": 1}
    assert open_thread_count_by_section([]) == {}


def test_threads_persisting_n_revisions_counts_distinct_revisions() -> None:
    threads = [
        {"id": "t1", "status": "open"},
        {"id": "t2", "status": "open"},
        {"id": "t3", "status": "resolved"},
    ]
    events = [
        {"thread_id": "t1", "revision_id": "r1"},
        {"thread_id": "t1", "revision_id": "r2"},
        {"thread_id": "t1", "revision_id": "r2"},  # duplicate revision
        {"thread_id": "t1", "revision_id": None},  # no revision attached
        {"thread_id": "t2", "revision_id": "r2"},
        {"thread_id": "t3", "revision_id": "r1"},  # resolved thread ignored
    ]

    assert threads_persisting_n_revisions(threads, events) == {"t1": 2, "t2": 1}


def test_first_pass_sections_lists_sections_never_raised() -> None:
    threads = [
        {"id": "t1", "section": "scan", "status": "resolved"},
        {"id": "t2", "section": "glenoid_implant", "status": "open"},
    ]

    result = first_pass_sections(threads)

    assert "scan" not in result
    assert "glenoid_implant" not in result
    assert "rider_form" in result
    assert len(result) == 6


def test_first_pass_sections_with_no_threads_returns_all_eight() -> None:
    assert len(first_pass_sections([])) == 8


def test_summarize_progress_aggregates_trainees() -> None:
    rows = [
        {
            "total_cases": 32,
            "approved_cases": 5,
            "overdue_cases": 2,
            "waiting_on_trainer": 3,
            "waiting_on_trainee": 4,
            "total_files": 96,
            "accepted_files": 14,
        },
        {
            "total_cases": 32,
            "approved_cases": 8,
            "overdue_cases": 0,
            "waiting_on_trainer": 1,
            "waiting_on_trainee": 0,
            "total_files": 96,
            "accepted_files": 24,
        },
    ]

    assert summarize_progress(rows) == ProgressTotals(
        trainees=2,
        total_cases=64,
        approved_cases=13,
        overdue_cases=2,
        waiting_on_trainer=4,
        waiting_on_trainee=4,
        total_files=192,
        accepted_files=38,
    )


def test_waiting_label_summarizes_next_action() -> None:
    assert (
        waiting_label(
            {
                "waiting_on_trainer": 2,
                "waiting_on_trainee": 1,
                "overdue_cases": 3,
            }
        )
        == "Packages in review: 2 · Files to send: 1 · Overdue tasks: 3"
    )
    assert waiting_label({"waiting_on_trainer": 0, "waiting_on_trainee": 0}) == "Clear"


def test_count_file_waiting_uses_to_send_sent_accepted() -> None:
    cases = [
        {
            "status": "assigned",
            "file_requirements": [
                {"status": "submitted"},
                {"status": "submitted"},
                {"status": "missing"},
            ],
        },
        {
            "status": "assigned",
            "file_requirements": [
                {"status": "missing"},
                {"status": "missing"},
                {"status": "missing"},
            ],
        },
    ]
    assert count_file_waiting(cases) == FileWaitingCounts(
        to_send=4,
        sent=2,
        accepted=0,
    )


def test_count_tasks_separates_open_and_with_trainer() -> None:
    cases = [
        {"status": "assigned", "due_date": "2099-01-01"},
        {"status": "submitted", "due_date": "2099-01-01"},
        {"status": "in_review", "due_date": "2099-01-01"},
        {"status": "approved", "due_date": "2099-01-01"},
        {"status": "assigned", "due_date": "2020-01-01"},
    ]
    assert count_tasks(cases) == TaskCounts(
        open_tasks=3,
        with_trainer=1,
        approved=1,
        overdue=1,
    )
