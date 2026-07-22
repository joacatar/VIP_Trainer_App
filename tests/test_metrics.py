from ct_training_tracker.metrics import (
    FileWaitingCounts,
    ProgressTotals,
    TaskCounts,
    count_file_waiting,
    count_tasks,
    summarize_progress,
    waiting_label,
)


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
        {"status": "in_review", "due_date": "2099-01-01"},
        {"status": "approved", "due_date": "2099-01-01"},
        {"status": "assigned", "due_date": "2020-01-01"},
    ]
    assert count_tasks(cases) == TaskCounts(
        open_tasks=2,
        with_trainer=1,
        approved=1,
        overdue=1,
    )
