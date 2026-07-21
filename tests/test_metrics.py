from ct_training_tracker.metrics import ProgressTotals, summarize_progress


def test_summarize_progress_aggregates_trainees() -> None:
    rows = [
        {
            "total_cases": 32,
            "approved_cases": 5,
            "overdue_cases": 2,
            "total_files": 96,
            "accepted_files": 14,
        },
        {
            "total_cases": 32,
            "approved_cases": 8,
            "overdue_cases": 0,
            "total_files": 96,
            "accepted_files": 24,
        },
    ]

    assert summarize_progress(rows) == ProgressTotals(
        trainees=2,
        total_cases=64,
        approved_cases=13,
        overdue_cases=2,
        total_files=192,
        accepted_files=38,
    )
