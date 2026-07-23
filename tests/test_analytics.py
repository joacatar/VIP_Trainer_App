from datetime import date

from ct_training_tracker.analytics import (
    build_planned_vs_actual,
    build_training_analytics,
    compute_first_pass_rate,
    compute_resubmission_events,
    estimate_phase_completion,
    format_days,
    format_rate,
    is_first_pass_case,
)


def _case(
    *,
    status: str,
    submit_count: int = 0,
    replacements: int = 0,
    revisions: int = 0,
    assigned_at: str | None = None,
    first_submitted_at: str | None = None,
    first_trainer_response_at: str | None = None,
    approved_at: str | None = None,
    due_date: str | None = None,
    schedule_due_date: str | None = None,
    trainee_name: str = "Ada",
    set_no: int = 1,
    case_no: int = 1,
) -> dict:
    return {
        "status": status,
        "submit_count": submit_count,
        "replacement_request_count": replacements,
        "revision_publish_count": revisions,
        "assigned_at": assigned_at,
        "first_submitted_at": first_submitted_at,
        "first_trainer_response_at": first_trainer_response_at,
        "approved_at": approved_at,
        "due_date": due_date,
        "schedule_due_date": schedule_due_date,
        "trainee_name": trainee_name,
        "set_no": set_no,
        "case_no": case_no,
    }


def test_first_pass_requires_clean_approval() -> None:
    clean = _case(status="approved", submit_count=1, replacements=0)
    dirty = _case(status="approved", submit_count=2, replacements=1)
    assert is_first_pass_case(clean)
    assert not is_first_pass_case(dirty)
    first, total, rate = compute_first_pass_rate([clean, dirty])
    assert (first, total, rate) == (1, 2, 0.5)


def test_resubmission_events_count_extra_submits() -> None:
    rows = [
        _case(status="in_review", submit_count=1),
        _case(status="awaiting_resubmission", submit_count=3),
    ]
    assert compute_resubmission_events(rows) == 2


def test_planned_vs_actual_delta() -> None:
    rows = [
        _case(
            status="approved",
            due_date="2026-07-10",
            approved_at="2026-07-12T12:00:00+00:00",
            set_no=1,
            case_no=4,
        )
    ]
    result = build_planned_vs_actual(rows)
    assert result == [
        {
            "trainee_name": "Ada",
            "set_no": 1,
            "case_no": 4,
            "catalog_label": "4A",
            "planned_due": "2026-07-10",
            "actual_approved": "2026-07-12",
            "days_delta": 2,
        }
    ]


def test_forecast_explains_missing_history() -> None:
    rows = [
        _case(status="assigned"),
        _case(status="assigned"),
    ]
    forecast = estimate_phase_completion(rows, today=date(2026, 7, 22))
    assert forecast.estimated_date is None
    assert forecast.remaining_cases == 2
    assert "not enough timestamped history" in forecast.explanation


def test_forecast_uses_observed_pace() -> None:
    rows = [
        _case(
            status="approved",
            assigned_at="2026-07-01T00:00:00+00:00",
            approved_at="2026-07-05T00:00:00+00:00",
        ),
        _case(
            status="approved",
            assigned_at="2026-07-01T00:00:00+00:00",
            approved_at="2026-07-09T00:00:00+00:00",
        ),
        _case(status="assigned"),
        _case(status="assigned"),
    ]
    forecast = estimate_phase_completion(rows, today=date(2026, 7, 22))
    assert forecast.avg_days_per_approved_case == 6.0
    assert forecast.remaining_cases == 2
    assert forecast.estimated_date == date(2026, 8, 3)
    assert "2 case(s) still open" in forecast.explanation


def test_build_training_analytics_aggregates() -> None:
    analytics = build_training_analytics(
        [
            _case(
                status="approved",
                submit_count=1,
                revisions=1,
                assigned_at="2026-07-01T00:00:00+00:00",
                first_submitted_at="2026-07-03T00:00:00+00:00",
                first_trainer_response_at="2026-07-04T00:00:00+00:00",
                approved_at="2026-07-05T00:00:00+00:00",
                due_date="2026-07-06",
            ),
            _case(status="in_review", submit_count=2, replacements=1, revisions=1),
        ],
        [
            {
                "section_key": "scapula",
                "correction_count": 4,
                "open_count": 1,
                "rolled_forward_count": 2,
            }
        ],
        label_for=lambda key: key.title(),
        today=date(2026, 7, 22),
    )
    assert analytics.first_pass_cases == 1
    assert analytics.published_revisions == 2
    assert analytics.resubmission_events == 1
    assert analytics.avg_trainee_turnaround_days == 2.0
    assert analytics.avg_trainer_turnaround_days == 1.0
    assert analytics.section_hotspots[0].label == "Scapula"
    assert format_rate(0.5) == "50%"
    assert format_days(1.5) == "1.5d"
