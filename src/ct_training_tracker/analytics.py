"""Event-derived training analytics and forecasting helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from statistics import mean
from typing import Any


@dataclass(frozen=True, slots=True)
class SectionHotspot:
    section_key: str
    label: str
    correction_count: int
    open_count: int
    rolled_forward_count: int


@dataclass(frozen=True, slots=True)
class ForecastResult:
    estimated_date: date | None
    remaining_cases: int
    avg_days_per_approved_case: float | None
    explanation: str


@dataclass(frozen=True, slots=True)
class TrainingAnalytics:
    cases_with_submit: int
    first_pass_cases: int
    first_pass_rate: float | None
    published_revisions: int
    resubmission_events: int
    avg_trainee_turnaround_days: float | None
    avg_trainer_turnaround_days: float | None
    planned_vs_actual: list[dict[str, Any]]
    section_hotspots: list[SectionHotspot]
    forecast: ForecastResult


def _as_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _as_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
    text = str(value).replace("Z", "+00:00")
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _days_between(start: object, end: object) -> float | None:
    start_dt = _as_datetime(start)
    end_dt = _as_datetime(end)
    if start_dt is None or end_dt is None:
        return None
    return max((end_dt - start_dt).total_seconds() / 86400.0, 0.0)


def is_first_pass_case(row: dict[str, Any]) -> bool:
    """Approved (or closed) without replacements and without a resubmit."""
    status = str(row.get("status") or "")
    if status != "approved":
        return False
    submit_count = int(row.get("submit_count") or 0)
    replacements = int(row.get("replacement_request_count") or 0)
    return submit_count <= 1 and replacements == 0


def compute_first_pass_rate(
    rows: list[dict[str, Any]],
) -> tuple[int, int, float | None]:
    submitted = [
        row
        for row in rows
        if int(row.get("submit_count") or 0) > 0 or row.get("status") == "approved"
    ]
    if not submitted:
        return 0, 0, None
    first_pass = sum(1 for row in submitted if is_first_pass_case(row))
    return first_pass, len(submitted), first_pass / len(submitted)


def compute_resubmission_events(rows: list[dict[str, Any]]) -> int:
    total = 0
    for row in rows:
        submits = int(row.get("submit_count") or 0)
        if submits > 1:
            total += submits - 1
    return total


def compute_average_turnaround_days(
    rows: list[dict[str, Any]],
    *,
    start_key: str,
    end_key: str,
) -> float | None:
    samples: list[float] = []
    for row in rows:
        days = _days_between(row.get(start_key), row.get(end_key))
        if days is not None:
            samples.append(days)
    if not samples:
        return None
    return round(mean(samples), 1)


def build_planned_vs_actual(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        if row.get("status") != "approved":
            continue
        planned = _as_date(row.get("due_date") or row.get("schedule_due_date"))
        actual = _as_date(row.get("approved_at"))
        if planned is None or actual is None:
            continue
        delta = (actual - planned).days
        result.append(
            {
                "trainee_name": row.get("trainee_name") or "Trainee",
                "set_no": row.get("set_no"),
                "case_no": row.get("case_no"),
                "catalog_label": row.get("catalog_label")
                or (
                    f"{row.get('case_no')}"
                    f"{'A' if row.get('set_no') == 1 else 'B'}"
                ),
                "planned_due": planned.isoformat(),
                "actual_approved": actual.isoformat(),
                "days_delta": delta,
            }
        )
    result.sort(
        key=lambda item: (
            str(item["trainee_name"]),
            item["set_no"],
            item["case_no"],
        )
    )
    return result


def build_section_hotspots(
    rows: list[dict[str, Any]],
    *,
    label_for,
) -> list[SectionHotspot]:
    hotspots = [
        SectionHotspot(
            section_key=str(row.get("section_key") or ""),
            label=label_for(str(row.get("section_key") or "")),
            correction_count=int(row.get("correction_count") or 0),
            open_count=int(row.get("open_count") or 0),
            rolled_forward_count=int(row.get("rolled_forward_count") or 0),
        )
        for row in rows
        if row.get("section_key")
    ]
    hotspots.sort(
        key=lambda item: (
            -item.correction_count,
            -item.rolled_forward_count,
            item.label,
        )
    )
    return hotspots


def estimate_phase_completion(
    rows: list[dict[str, Any]],
    *,
    today: date | None = None,
) -> ForecastResult:
    """Estimate remaining work from observed days between assign and approve."""
    today = today or date.today()
    total = len(rows)
    approved = [row for row in rows if row.get("status") == "approved"]
    remaining = total - len(approved)

    durations: list[float] = []
    for row in approved:
        days = _days_between(row.get("assigned_at"), row.get("approved_at"))
        if days is None:
            days = _days_between(row.get("first_submitted_at"), row.get("approved_at"))
        if days is not None:
            durations.append(days)

    if remaining <= 0:
        return ForecastResult(
            estimated_date=today,
            remaining_cases=0,
            avg_days_per_approved_case=round(mean(durations), 1) if durations else None,
            explanation="All tracked cases are already approved.",
        )
    if not durations:
        return ForecastResult(
            estimated_date=None,
            remaining_cases=remaining,
            avg_days_per_approved_case=None,
            explanation=(
                f"{remaining} cases remain, but there is not enough timestamped "
                "history yet (need assign→approve or submit→approve events)."
            ),
        )

    avg_days = mean(durations)
    estimated = today + timedelta(days=round(avg_days * remaining))
    return ForecastResult(
        estimated_date=estimated,
        remaining_cases=remaining,
        avg_days_per_approved_case=round(avg_days, 1),
        explanation=(
            f"Based on {len(durations)} approved case(s) averaging "
            f"{avg_days:.1f} days each; {remaining} case(s) still open."
        ),
    )


def build_training_analytics(
    case_rows: list[dict[str, Any]],
    section_rows: list[dict[str, Any]],
    *,
    label_for,
    today: date | None = None,
) -> TrainingAnalytics:
    first_pass, with_submit, rate = compute_first_pass_rate(case_rows)
    return TrainingAnalytics(
        cases_with_submit=with_submit,
        first_pass_cases=first_pass,
        first_pass_rate=rate,
        published_revisions=sum(
            int(row.get("revision_publish_count") or 0) for row in case_rows
        ),
        resubmission_events=compute_resubmission_events(case_rows),
        avg_trainee_turnaround_days=compute_average_turnaround_days(
            case_rows,
            start_key="assigned_at",
            end_key="first_submitted_at",
        ),
        avg_trainer_turnaround_days=compute_average_turnaround_days(
            case_rows,
            start_key="first_submitted_at",
            end_key="first_trainer_response_at",
        ),
        planned_vs_actual=build_planned_vs_actual(case_rows),
        section_hotspots=build_section_hotspots(section_rows, label_for=label_for),
        forecast=estimate_phase_completion(case_rows, today=today),
    )


def format_rate(rate: float | None) -> str:
    if rate is None:
        return "—"
    return f"{rate * 100:.0f}%"


def format_days(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.1f}d"
