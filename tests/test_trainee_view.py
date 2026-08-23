from ct_training_tracker.metrics import case_owner, next_step
from ct_training_tracker.views.case_board import (
    apply_case_filter,
    enrich_cases,
    file_progress,
    pick_next_case,
    sort_case_rows,
)


def test_file_progress_shows_ready_and_to_send() -> None:
    requirements = [
        {"kind": "pdf_primary", "status": "accepted"},
        {"kind": "pdf_secondary", "status": "submitted"},
        {"kind": "ov", "status": "missing"},
    ]

    assert file_progress(requirements) == "2 ready · 1 to send"


def test_enrich_cases_merges_notes_into_case_rows() -> None:
    cases = [
        {
            "id": "case-1",
            "set_no": 1,
            "case_no": 1,
            "status": "assigned",
            "due_date": "2026-07-28",
            "schedule_due_date": "2026-07-27",
            "file_requirements": [
                {"status": "missing"},
                {"status": "missing"},
                {"status": "missing"},
            ],
        }
    ]
    assignments = [
        {
            "case_id": "case-1",
            "instructions": "Focus on landmarking.",
            "cases": {"set_no": 1, "case_no": 1},
        }
    ]

    frame = enrich_cases(cases, assignments, role="trainee")

    assert frame.iloc[0]["notes"] == "Focus on landmarking."
    assert frame.iloc[0]["catalog_label"] == "1A"
    assert frame.iloc[0]["order_number"] == "12-26-02-0002"
    assert frame.iloc[0]["status"] == "Assigned"
    assert frame.iloc[0]["files"] == "0 ready · 3 to send"
    assert frame.iloc[0]["owner"] == "trainee"
    assert frame.iloc[0]["next_step"] == "Prepare files and submit package"


def test_pick_next_case_prefers_needs_you() -> None:
    cases = [
        {
            "id": "a",
            "set_no": 1,
            "case_no": 1,
            "status": "in_review",
            "due_date": "2026-08-01",
            "file_requirements": [],
        },
        {
            "id": "b",
            "set_no": 1,
            "case_no": 2,
            "status": "assigned",
            "due_date": "2026-08-05",
            "file_requirements": [],
        },
        {
            "id": "c",
            "set_no": 1,
            "case_no": 3,
            "status": "assigned",
            "due_date": "2026-08-02",
            "file_requirements": [],
        },
    ]
    frame = enrich_cases(cases, [], role="trainee")
    next_case = pick_next_case(frame, role="trainee")
    assert next_case is not None
    assert next_case["id"] == "c"


def test_apply_case_filter_is_role_aware() -> None:
    cases = [
        {
            "id": "a",
            "set_no": 1,
            "case_no": 1,
            "status": "assigned",
            "due_date": "2026-08-01",
            "file_requirements": [],
        },
        {
            "id": "b",
            "set_no": 1,
            "case_no": 2,
            "status": "in_review",
            "due_date": "2026-08-01",
            "file_requirements": [],
        },
        {
            "id": "c",
            "set_no": 1,
            "case_no": 3,
            "status": "not_started",
            "due_date": "2026-08-01",
            "file_requirements": [],
        },
        {
            "id": "d",
            "set_no": 1,
            "case_no": 4,
            "status": "submitted",
            "due_date": "2026-08-01",
            "file_requirements": [],
        },
    ]
    trainee_frame = enrich_cases(cases, [], role="trainee")
    trainer_frame = enrich_cases(cases, [], role="trainer")

    assert list(
        apply_case_filter(trainee_frame, "needs_you", role="trainee")["id"]
    ) == ["a", "d"]
    assert list(
        apply_case_filter(trainee_frame, "with_other", role="trainee")["id"]
    ) == ["b"]
    assert list(
        apply_case_filter(trainer_frame, "needs_you", role="trainer")["id"]
    ) == ["b", "c"]
    assert list(
        apply_case_filter(trainer_frame, "with_other", role="trainer")["id"]
    ) == ["a", "d"]
    assert list(sort_case_rows(trainee_frame, role="trainee")["id"]) == [
        "a",
        "d",
        "b",
        "c",
    ]


def test_case_owner_and_next_step() -> None:
    assert case_owner("assigned") == "trainee"
    assert case_owner("submitted") == "trainee"
    assert case_owner("in_review") == "trainer"
    assert case_owner("not_started") == "trainer"
    assert case_owner("approved") == "none"
    assert next_step("in_review", role="trainer") == "Review package"
    assert next_step("in_review", role="trainee") == "Waiting on trainer"
    assert next_step("not_started", role="trainer") == "Assign this case"


def test_enrich_cases_carries_phase_2_columns() -> None:
    cases = [
        {
            "id": "case-l06",
            "phase_no": 2,
            "set_no": 1,
            "case_no": 6,
            "catalog_label": "L06",
            "order_number": "12-26-07-0005",
            "journey_category": "Manual",
            "instruction": "Reject and plan manually for practice",
            "released_on": "2026-09-01",
            "status": "assigned",
            "due_date": "2026-09-02",
            "schedule_due_date": "2026-09-02",
            "file_requirements": [],
        }
    ]

    frame = enrich_cases(cases, [], role="trainee")
    row = frame.iloc[0]

    assert row["phase_no"] == 2
    assert row["journey_category"] == "Manual"
    assert row["instruction"] == "Reject and plan manually for practice"
    assert row["released_on"] == "2026-09-01"


def test_enrich_cases_defaults_phase_no_for_legacy_rows() -> None:
    cases = [
        {
            "id": "case-1",
            "set_no": 1,
            "case_no": 1,
            "status": "assigned",
            "due_date": "2026-07-28",
            "schedule_due_date": "2026-07-27",
            "file_requirements": [],
        }
    ]

    frame = enrich_cases(cases, [], role="trainee")

    assert frame.iloc[0]["phase_no"] == 1


def test_enrich_cases_never_lets_a_missing_instruction_become_truthy() -> None:
    """Regression: a None mixed into a pandas string column round-trips as
    NaN — and NaN is truthy in Python. Needs two rows through one DataFrame
    to trigger the dtype coercion; a single hand-built dict would not catch
    this the way going through enrich_cases() does."""
    cases = [
        {
            "id": "case-plain",
            "phase_no": 2,
            "set_no": 1,
            "case_no": 1,
            "catalog_label": "L01",
            "instruction": None,
            "status": "not_started",
            "due_date": "2026-08-25",
            "schedule_due_date": "2026-08-25",
            "file_requirements": [],
        },
        {
            "id": "case-manual",
            "phase_no": 2,
            "set_no": 1,
            "case_no": 6,
            "catalog_label": "L06",
            "instruction": "Reject and plan manually for practice",
            "status": "not_started",
            "due_date": "2026-08-26",
            "schedule_due_date": "2026-08-26",
            "file_requirements": [],
        },
    ]

    frame = enrich_cases(cases, [], role="trainee")
    plain_row = frame.iloc[0].to_dict()
    manual_row = frame.iloc[1].to_dict()

    assert not plain_row["instruction"]
    assert manual_row["instruction"] == "Reject and plan manually for practice"
