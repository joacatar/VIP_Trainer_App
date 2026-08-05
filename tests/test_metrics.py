from ct_training_tracker.metrics import (
    FileWaitingCounts,
    ProgressTotals,
    TaskCounts,
    count_file_waiting,
    count_tasks,
    first_pass_sections,
    open_thread_count_by_section,
    summarize_progress,
    threads_persisting_n_revisions,
    waiting_label,
)


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
