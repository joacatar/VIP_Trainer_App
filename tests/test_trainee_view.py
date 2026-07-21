from ct_training_tracker.views.case_board import enrich_cases, file_progress


def test_file_progress_counts_only_accepted_requirements() -> None:
    requirements = [
        {"kind": "pdf_primary", "status": "accepted"},
        {"kind": "pdf_secondary", "status": "replacement_requested"},
        {"kind": "ov", "status": "missing"},
    ]

    assert file_progress(requirements) == "1 / 3 accepted"


def test_enrich_cases_merges_notes_into_case_rows() -> None:
    cases = [
        {
            "id": "case-1",
            "set_no": 1,
            "case_no": 1,
            "status": "assigned",
            "due_date": "2026-07-28",
            "schedule_due_date": "2026-07-27",
            "file_requirements": [{"status": "missing"}],
        }
    ]
    assignments = [
        {
            "case_id": "case-1",
            "instructions": "Focus on landmarking.",
            "cases": {"set_no": 1, "case_no": 1},
        }
    ]

    frame = enrich_cases(cases, assignments)

    assert frame.iloc[0]["notes"] == "Focus on landmarking."
    assert frame.iloc[0]["status"] == "Assigned"
