from ct_training_tracker.views.trainee import _file_progress


def test_file_progress_counts_only_accepted_requirements() -> None:
    requirements = [
        {"kind": "pdf_primary", "status": "accepted"},
        {"kind": "pdf_secondary", "status": "replacement_requested"},
        {"kind": "ov", "status": "missing"},
    ]

    assert _file_progress(requirements) == "1 / 3 accepted"
