"""Unit tests for Feature 7 coaching analytics metrics."""

from __future__ import annotations

import datetime as dt

from ct_training_tracker.metrics import (
    avg_days_per_case_by_trainee,
    est_completion_by_trainee,
    first_pass_rate_by_trainee,
    first_pass_trend,
    hardest_cases,
    recurring_issues,
    regression_rate,
    section_correction_rates,
)

TODAY = dt.date(2026, 8, 5)


def test_hardest_cases_ranks_by_count_and_breaks_ties() -> None:
    threads = [
        {"id": "1", "case_id": "a"},
        {"id": "2", "case_id": "a"},
        {"id": "3", "case_id": "b"},
        {"id": "4", "case_id": "c"},
        {"id": "5", "case_id": "c"},
    ]
    cases = [
        {"id": "a", "trainee_name": "Ann"},
        {"id": "b", "trainee_name": "Bob"},
        {"id": "c", "trainee_name": "Cara"},
    ]
    ranked = hardest_cases(threads, cases, top_n=5)
    assert [row["case_id"] for row in ranked] == ["a", "c", "b"]
    assert ranked[0]["count"] == 2
    assert ranked[0]["trainee"] == "Ann"


def test_hardest_cases_empty_and_top_n() -> None:
    assert hardest_cases([], top_n=5) == []
    threads = [{"id": str(i), "case_id": f"c{i}"} for i in range(6)]
    ranked = hardest_cases(threads, top_n=3)
    assert len(ranked) == 3


def test_hardest_cases_missing_case_id_skipped() -> None:
    threads = [{"id": "1"}, {"id": "2", "case_id": "x"}]
    ranked = hardest_cases(threads, top_n=5)
    assert ranked == [{"case_id": "x", "trainee": "", "count": 1}]


def test_recurring_issues_requires_min_cases() -> None:
    threads = [
        {
            "id": "1",
            "case_id": "a",
            "correction_events": [{"event_type": "raised", "body": "Fix FOV!!"}],
        },
        {
            "id": "2",
            "case_id": "b",
            "correction_events": [{"event_type": "raised", "body": "fix fov"}],
        },
        {
            "id": "3",
            "case_id": "c",
            "correction_events": [{"event_type": "raised", "body": "Fix FOV."}],
        },
        {
            "id": "4",
            "case_id": "d",
            "correction_events": [{"event_type": "raised", "body": "Only once"}],
        },
    ]
    groups = recurring_issues(threads, min_cases=3, top_n=10)
    assert len(groups) == 1
    assert groups[0]["normalized_text"] == "fix fov"
    assert groups[0]["case_count"] == 3


def test_recurring_issues_ignores_empty_bodies() -> None:
    threads = [
        {"id": "1", "case_id": "a", "correction_events": []},
        {"id": "2", "case_id": "b", "body": ""},
    ]
    assert recurring_issues(threads, min_cases=1) == []


def test_recurring_issues_single_case_excluded() -> None:
    threads = [
        {
            "id": "1",
            "case_id": "a",
            "correction_events": [{"event_type": "raised", "body": "Same"}],
        },
        {
            "id": "2",
            "case_id": "a",
            "correction_events": [{"event_type": "raised", "body": "Same"}],
        },
    ]
    assert recurring_issues(threads, min_cases=2) == []


def test_regression_rate_detects_reopen_after_resolved() -> None:
    threads = [{"id": "t1"}, {"id": "t2"}, {"id": "t3"}]
    events = [
        {"thread_id": "t1", "event_type": "raised", "created_at": "1"},
        {"thread_id": "t1", "event_type": "resolved", "created_at": "2"},
        {"thread_id": "t1", "event_type": "still_open", "created_at": "3"},
        {"thread_id": "t2", "event_type": "raised", "created_at": "1"},
        {"thread_id": "t2", "event_type": "resolved", "created_at": "2"},
        {"thread_id": "t3", "event_type": "still_open", "created_at": "1"},
    ]
    assert regression_rate(threads, events) == 1 / 3


def test_regression_rate_empty_and_nested_events() -> None:
    assert regression_rate([]) == 0.0
    threads = [
        {
            "id": "t1",
            "correction_events": [
                {"event_type": "resolved", "created_at": "1"},
                {"event_type": "still_open", "created_at": "2"},
            ],
        }
    ]
    assert regression_rate(threads) == 1.0


def test_regression_rate_no_events_is_zero() -> None:
    assert regression_rate([{"id": "t1", "correction_events": []}]) == 0.0


def test_first_pass_rate_by_trainee() -> None:
    cases = [
        {"id": "1", "trainee_id": "A"},
        {"id": "2", "trainee_id": "A"},
        {"id": "3", "trainee_id": "B"},
    ]
    threads = [{"id": "t", "case_id": "1"}]
    rates = first_pass_rate_by_trainee(threads, cases)
    assert rates["A"] == 0.5
    assert rates["B"] == 1.0


def test_first_pass_rate_trainee_with_zero_cases() -> None:
    assert first_pass_rate_by_trainee([], []) == {}


def test_first_pass_rate_all_have_threads() -> None:
    cases = [{"id": "1", "trainee_id": "A"}]
    threads = [{"id": "t", "case_id": "1"}]
    assert first_pass_rate_by_trainee(threads, cases)["A"] == 0.0


def test_first_pass_trend_groups_by_window() -> None:
    cases = [
        {"id": str(i), "trainee_id": "A", "case_no": i} for i in range(1, 6)
    ]
    threads = [{"id": "t", "case_id": "1"}, {"id": "t2", "case_id": "2"}]
    trend = first_pass_trend(threads, cases, window=2)
    assert trend["A"] == [0.0, 1.0, 1.0]


def test_first_pass_trend_empty_trainee() -> None:
    assert first_pass_trend([], [], window=10) == {}


def test_first_pass_trend_partial_window() -> None:
    cases = [{"id": "1", "trainee_id": "A", "case_no": 1}]
    assert first_pass_trend([], cases, window=10)["A"] == [1.0]


def test_est_completion_by_trainee_and_avg_days() -> None:
    cases = [
        {
            "id": "1",
            "trainee_id": "A",
            "status": "approved",
            "assigned_at": "2026-01-01",
            "approved_at": "2026-01-11",
        },
        {
            "id": "2",
            "trainee_id": "A",
            "status": "assigned",
        },
        {"id": "3", "trainee_id": "B", "status": "approved"},
    ]
    forecasts = est_completion_by_trainee(cases, today=TODAY)
    assert forecasts["A"] == TODAY + dt.timedelta(days=10)
    assert forecasts["B"] == TODAY
    assert avg_days_per_case_by_trainee(cases)["A"] == 10.0


def test_est_completion_no_history() -> None:
    cases = [
        {"id": "1", "trainee_id": "A", "status": "assigned"},
        {"id": "2", "trainee_id": "A", "status": "assigned"},
    ]
    assert est_completion_by_trainee(cases, today=TODAY)["A"] is None


def test_est_completion_zero_cases_trainee_absent() -> None:
    assert est_completion_by_trainee([], today=TODAY) == {}


def test_section_correction_rates() -> None:
    cases = [{"id": "1"}, {"id": "2"}]
    threads = [
        {"id": "t1", "case_id": "1", "section": "scan", "status": "open"},
        {"id": "t2", "case_id": "2", "section": "scan", "status": "resolved"},
    ]
    rows = section_correction_rates(threads, cases)
    scan = next(row for row in rows if row["section_key"] == "scan")
    assert scan["correction_count"] == 2
    assert scan["case_count"] == 2
    assert scan["case_share"] == 1.0
    assert scan["open_count"] == 1
