from dataclasses import dataclass
from datetime import date, timedelta
from statistics import mean
from typing import Any, Literal

from ct_training_tracker.case_labels import case_catalog_label
from ct_training_tracker.revisions import REVIEW_SECTIONS

CaseOwner = Literal["trainee", "trainer", "none"]
AppRole = Literal["trainee", "trainer"]
AttentionState = Literal["assigned", "with_trainee", "needs_trainer", "approved"]

ACTIVE_CASE_STATUSES = {
    "assigned",
    "submitted",
    "awaiting_resubmission",
    "in_review",
    "corrections_sent",
}
# Trainee still owns the case until they notify the trainer for review.
TRAINEE_OWNED_STATUSES = frozenset(
    {"assigned", "submitted", "awaiting_resubmission"}
)
# Trainer must assign, review a package, or continue after publishing feedback.
TRAINER_OWNED_STATUSES = frozenset(
    {"not_started", "in_review", "corrections_sent"}
)
OPEN_TASK_STATUSES = set(TRAINEE_OWNED_STATUSES)
TASK_WITH_TRAINER_STATUSES = {"in_review", "corrections_sent"}
TRAINEE_FILE_TODO = {"missing", "replacement_requested"}
TRAINER_FILE_TODO = {"under_review"}
SENT_FILE_STATUSES = {"submitted", "under_review"}
UPLOADED_FILE_STATUSES = {
    "submitted",
    "under_review",
    "accepted",
    "replacement_requested",
}

_NEXT_STEP: dict[tuple[str, AppRole], str] = {
    ("not_started", "trainer"): "Assign this case",
    ("not_started", "trainee"): "Waiting for assignment",
    ("assigned", "trainee"): "Prepare files and submit package",
    ("assigned", "trainer"): "Waiting on trainee",
    ("submitted", "trainee"): "Submit package for review",
    ("submitted", "trainer"): "Waiting on trainee",
    ("awaiting_resubmission", "trainee"): "Replace requested files",
    ("awaiting_resubmission", "trainer"): "Waiting on trainee",
    ("in_review", "trainer"): "Review package",
    ("in_review", "trainee"): "Waiting on trainer",
    ("corrections_sent", "trainer"): "Continue review or wait",
    ("corrections_sent", "trainee"): "Read feedback",
    ("approved", "trainer"): "Done",
    ("approved", "trainee"): "Done",
}


def case_owner(status: str) -> CaseOwner:
    """Who must take the next case-level action."""
    if status in TRAINEE_OWNED_STATUSES:
        return "trainee"
    if status in TRAINER_OWNED_STATUSES:
        return "trainer"
    return "none"


def next_step(status: str, *, role: AppRole) -> str:
    """Short role-aware call-to-action for inbox rows and headers."""
    return _NEXT_STEP.get((status, role), "No action needed")


def owned_by_statuses(role: AppRole) -> frozenset[str]:
    if role == "trainer":
        return TRAINER_OWNED_STATUSES
    return TRAINEE_OWNED_STATUSES


def waiting_on_other_statuses(role: AppRole) -> frozenset[str]:
    """Statuses where the other party owns the next action."""
    if role == "trainer":
        return TRAINEE_OWNED_STATUSES
    # Trainee should not treat unassigned cases as "with trainer".
    return frozenset({"in_review", "corrections_sent"})


@dataclass(frozen=True, slots=True)
class ProgressTotals:
    trainees: int
    total_cases: int
    approved_cases: int
    overdue_cases: int
    waiting_on_trainer: int
    waiting_on_trainee: int
    total_files: int
    accepted_files: int


@dataclass(frozen=True, slots=True)
class TaskCounts:
    open_tasks: int
    with_trainer: int
    approved: int
    overdue: int


@dataclass(frozen=True, slots=True)
class FileWaitingCounts:
    to_send: int
    sent: int
    accepted: int


def summarize_progress(rows: list[dict[str, Any]]) -> ProgressTotals:
    return ProgressTotals(
        trainees=len(rows),
        total_cases=sum(int(row["total_cases"]) for row in rows),
        approved_cases=sum(int(row["approved_cases"]) for row in rows),
        overdue_cases=sum(int(row["overdue_cases"]) for row in rows),
        waiting_on_trainer=sum(int(row.get("waiting_on_trainer", 0)) for row in rows),
        waiting_on_trainee=sum(int(row.get("waiting_on_trainee", 0)) for row in rows),
        total_files=sum(int(row["total_files"]) for row in rows),
        accepted_files=sum(int(row["accepted_files"]) for row in rows),
    )


def count_tasks(cases: list[dict[str, Any]]) -> TaskCounts:
    open_tasks = 0
    with_trainer = 0
    approved = 0
    overdue = 0
    for case in cases:
        status = case.get("status")
        if status in OPEN_TASK_STATUSES:
            open_tasks += 1
        elif status in TASK_WITH_TRAINER_STATUSES:
            with_trainer += 1
        elif status == "approved":
            approved += 1
        due = case.get("due_date") or case.get("schedule_due_date")
        if status != "approved" and due:
            try:
                from datetime import date

                if date.fromisoformat(str(due)) < date.today():
                    overdue += 1
            except ValueError:
                pass
    return TaskCounts(
        open_tasks=open_tasks,
        with_trainer=with_trainer,
        approved=approved,
        overdue=overdue,
    )


def count_file_waiting(cases: list[dict[str, Any]]) -> FileWaitingCounts:
    """File-slot counts: to send / sent / accepted."""
    to_send = 0
    sent = 0
    accepted = 0
    for case in cases:
        requirements = case.get("file_requirements") or []
        if not isinstance(requirements, list):
            continue
        active = case.get("status") in ACTIVE_CASE_STATUSES
        for requirement in requirements:
            if not isinstance(requirement, dict):
                continue
            status = requirement.get("status")
            if status == "accepted":
                accepted += 1
            elif status in SENT_FILE_STATUSES:
                sent += 1
            elif active and status in TRAINEE_FILE_TODO:
                to_send += 1
    return FileWaitingCounts(to_send=to_send, sent=sent, accepted=accepted)


def file_slot_label(status: str) -> str:
    if status == "accepted":
        return "Accepted"
    if status == "under_review":
        return "With trainer"
    if status == "submitted":
        return "Ready"
    if status == "replacement_requested":
        return "To send (replace)"
    if status == "missing":
        return "To send"
    return str(status).replace("_", " ").title()


@dataclass(frozen=True, slots=True)
class CaseAttention:
    state: AttentionState
    overdue: bool
    has_open_question: bool
    needs_assignment: bool


def case_attention_state(
    case: dict[str, Any],
    revisions: list[dict[str, Any]],
    threads: list[dict[str, Any]],
    questions: list[dict[str, Any]],
    today: date,
) -> CaseAttention:
    """Single source of truth for who owns a case right now.

    States: 'assigned' (scheduled/first-pass prep with the trainee),
    'with_trainee' (sent back for rework), 'needs_trainer' (package waiting
    for review, or a review draft is in progress), 'approved'.
    """
    status = str(case.get("status") or "")
    has_draft = any(
        str(revision.get("status") or "") == "draft" for revision in revisions
    )
    has_open_thread = any(
        str(thread.get("status") or "open") == "open" for thread in threads
    )

    state: AttentionState
    if status == "approved":
        state = "approved"
    elif status == "in_review" or (status == "corrections_sent" and has_draft):
        state = "needs_trainer"
    elif status in {"corrections_sent", "awaiting_resubmission"} or (
        status in {"assigned", "submitted"} and has_open_thread
    ):
        state = "with_trainee"
    else:  # not_started, assigned, submitted
        state = "assigned"

    overdue = False
    due_raw = case.get("due_date")
    if state != "approved" and due_raw:
        try:
            overdue = date.fromisoformat(str(due_raw)) < today
        except ValueError:
            pass

    has_open_question = any(
        str(question.get("status") or "") == "open" for question in questions
    )
    return CaseAttention(
        state=state,
        overdue=overdue,
        has_open_question=has_open_question,
        needs_assignment=status == "not_started",
    )


def board_card_badge(
    attention: CaseAttention,
    *,
    due_date: str | None,
    has_open_question: bool,
    today: date,
) -> tuple[str, str] | None:
    """At most ONE (label, color) badge per kanban card.

    Priority: Overdue > Due today > Question open. Approved cards get none.
    """
    if attention.state == "approved":
        return None
    if attention.overdue:
        return ("Overdue", "red")
    if due_date:
        try:
            if date.fromisoformat(str(due_date)) == today:
                return ("Due today", "orange")
        except ValueError:
            pass
    if has_open_question or attention.has_open_question:
        return ("Question", "orange")
    return None


BOARD_LANES: tuple[tuple[AttentionState, str], ...] = (
    ("assigned", "Assigned"),
    ("with_trainee", "With trainee"),
    ("needs_trainer", "Needs you"),
    ("approved", "Approved"),
)

APPROVED_VISIBLE = 2


@dataclass(frozen=True, slots=True)
class BoardCard:
    case_id: str
    trainee_id: str
    trainee_name: str
    case_label: str
    set_no: int
    state: AttentionState
    due_date: str | None
    badge_label: str | None
    badge_color: str | None
    footer: str
    footer_urgent: bool
    open_question_count: int
    needs_assignment: bool


def _format_short_date(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        value = date.fromisoformat(str(raw)[:10])
    except ValueError:
        return str(raw)[:10]
    return f"{value.strftime('%b')} {value.day}"


def board_card_footer(
    attention: CaseAttention,
    *,
    due_date: str | None,
    open_question_count: int,
    revision_sent_at: str | None = None,
) -> tuple[str, bool]:
    """(footer text, urgent). Urgent marks overdue due dates in red."""
    if attention.state == "approved":
        return ("", False)
    if attention.state == "needs_trainer" and open_question_count:
        noun = "question" if open_question_count == 1 else "questions"
        return (f"{open_question_count} open {noun}", False)
    if attention.state == "with_trainee":
        sent = _format_short_date(revision_sent_at)
        if sent:
            return (f"Revision sent {sent}", False)
        return ("Awaiting trainee", False)
    due = _format_short_date(due_date)
    if due:
        return (f"Due {due}", attention.overdue)
    if attention.needs_assignment:
        return ("Needs assignment", False)
    return ("", False)


def build_board_card(
    case: dict[str, Any],
    *,
    trainee_name: str,
    today: date,
    open_questions: list[dict[str, Any]] | None = None,
    revisions: list[dict[str, Any]] | None = None,
    threads: list[dict[str, Any]] | None = None,
) -> BoardCard:
    """One kanban card from a case row + optional related rows."""
    questions = open_questions or []
    attention = case_attention_state(
        case,
        revisions or [],
        threads or [],
        questions,
        today,
    )
    due = case.get("due_date") or case.get("schedule_due_date")
    due_str = str(due)[:10] if due else None
    open_q = sum(1 for q in questions if str(q.get("status") or "") == "open")
    badge = board_card_badge(
        attention,
        due_date=due_str,
        has_open_question=open_q > 0,
        today=today,
    )
    published = [
        r
        for r in (revisions or [])
        if str(r.get("status") or "") == "published" and r.get("published_at")
    ]
    published.sort(key=lambda r: str(r.get("published_at") or ""), reverse=True)
    revision_sent = (
        str(published[0]["published_at"])[:10] if published else None
    )
    footer, urgent = board_card_footer(
        attention,
        due_date=due_str,
        open_question_count=open_q,
        revision_sent_at=revision_sent,
    )
    label = f"Case {case_catalog_label(case)}"
    return BoardCard(
        case_id=str(case["id"]),
        trainee_id=str(case.get("trainee_id") or ""),
        trainee_name=trainee_name,
        case_label=label,
        set_no=int(case.get("set_no") or 0),
        state=attention.state,
        due_date=due_str,
        badge_label=badge[0] if badge else None,
        badge_color=badge[1] if badge else None,
        footer=footer,
        footer_urgent=urgent,
        open_question_count=open_q,
        needs_assignment=attention.needs_assignment,
    )


def group_board_cards(
    cards: list[BoardCard],
) -> dict[AttentionState, list[BoardCard]]:
    """Partition cards into the four kanban lanes, sorted for scanability."""
    lanes: dict[AttentionState, list[BoardCard]] = {
        state: [] for state, _label in BOARD_LANES
    }
    for card in cards:
        lanes[card.state].append(card)

    def due_key(card: BoardCard) -> str:
        return card.due_date or "9999-99-99"

    for state in lanes:
        if state == "needs_trainer":
            lanes[state].sort(
                key=lambda c: (
                    0 if c.badge_label == "Overdue" else 1,
                    0 if c.badge_label == "Due today" else 1,
                    0 if c.badge_label == "Question" else 1,
                    due_key(c),
                    c.case_label,
                )
            )
        elif state == "approved":
            lanes[state].sort(key=lambda c: (c.set_no, c.case_label))
        else:
            lanes[state].sort(key=lambda c: (due_key(c), c.case_label))
    return lanes


TrainerCaseBucket = Literal["needs_you", "with_other", "approved"]


def trainer_case_bucket(status: str) -> TrainerCaseBucket:
    """Cases-page filter bucket for one case, derived from
    case_attention_state so filters and dashboard chips cannot disagree."""
    attention = case_attention_state(
        {"status": status}, [], [], [], date.today()
    )
    if attention.state == "needs_trainer" or attention.needs_assignment:
        return "needs_you"
    if attention.state == "approved":
        return "approved"
    return "with_other"


def open_thread_count_by_section(
    threads: list[dict[str, Any]],
) -> dict[str, int]:
    """Open correction-thread counts keyed by section."""
    counts: dict[str, int] = {}
    for thread in threads:
        if thread.get("status") != "open":
            continue
        section = str(thread.get("section") or "")
        counts[section] = counts.get(section, 0) + 1
    return counts


def threads_persisting_n_revisions(
    threads: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> dict[str, int]:
    """Distinct revisions each open thread has survived, keyed by thread id."""
    revisions_by_thread: dict[str, set[str]] = {
        str(thread["id"]): set()
        for thread in threads
        if thread.get("status") == "open"
    }
    for event in events:
        thread_id = str(event.get("thread_id") or "")
        revision_id = event.get("revision_id")
        if thread_id in revisions_by_thread and revision_id:
            revisions_by_thread[thread_id].add(str(revision_id))
    return {
        thread_id: len(revision_ids)
        for thread_id, revision_ids in revisions_by_thread.items()
    }


def first_pass_sections(threads: list[dict[str, Any]]) -> list[str]:
    """Sections that never had a correction thread raised."""
    raised = {str(thread.get("section") or "") for thread in threads}
    return [key for key, _label, _order in REVIEW_SECTIONS if key not in raised]


def waiting_label(row: dict[str, Any]) -> str:
    """Human-readable next-action summary for one trainee."""
    packages = int(row.get("waiting_on_trainer", 0))
    to_send = int(row.get("waiting_on_trainee", 0))
    overdue = int(row.get("overdue_cases", 0))

    parts: list[str] = []
    if packages:
        parts.append(f"Packages in review: {packages}")
    if to_send:
        parts.append(f"Files to send: {to_send}")
    if overdue:
        parts.append(f"Overdue tasks: {overdue}")
    return " · ".join(parts) if parts else "Clear"


# --- Feature 7 analytics (thread-based coaching metrics) ---


def _normalize_issue_text(text: str) -> str:
    lowered = text.lower().strip()
    cleaned = "".join(
        ch if ch.isalnum() or ch.isspace() else " " for ch in lowered
    )
    return " ".join(cleaned.split())


def _thread_raised_body(thread: dict[str, Any]) -> str:
    events = list(thread.get("correction_events") or [])
    if not events and thread.get("event_type") == "raised":
        return str(thread.get("body") or "")
    raised = next(
        (event for event in events if event.get("event_type") == "raised"),
        None,
    )
    if raised is not None:
        return str(raised.get("body") or "")
    if events:
        return str(events[0].get("body") or "")
    return str(thread.get("body") or "")


def _flatten_events(
    threads: list[dict[str, Any]],
    events: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    if events is not None:
        return list(events)
    flat: list[dict[str, Any]] = []
    for thread in threads:
        thread_id = str(thread.get("id") or "")
        for event in thread.get("correction_events") or []:
            flat.append({**event, "thread_id": event.get("thread_id") or thread_id})
    return flat


def hardest_cases(
    threads: list[dict[str, Any]],
    cases: list[dict[str, Any]] | None = None,
    *,
    top_n: int = 5,
) -> list[dict[str, Any]]:
    """Cases ranked by total correction-thread count (open + resolved)."""
    cases = cases or []
    trainee_by_case = {
        str(case.get("id") or case.get("case_id") or ""): str(
            case.get("trainee_name")
            or case.get("trainee")
            or case.get("trainee_id")
            or ""
        )
        for case in cases
    }
    counts: dict[str, int] = {}
    for thread in threads:
        case_id = str(thread.get("case_id") or "")
        if not case_id:
            continue
        counts[case_id] = counts.get(case_id, 0) + 1

    ranked = sorted(
        counts.items(),
        key=lambda item: (-item[1], item[0]),
    )
    result: list[dict[str, Any]] = []
    for case_id, count in ranked[:top_n]:
        trainee = trainee_by_case.get(case_id, "")
        if not trainee:
            for thread in threads:
                if str(thread.get("case_id")) == case_id:
                    trainee = str(
                        thread.get("trainee_name")
                        or thread.get("trainee")
                        or ""
                    )
                    break
        result.append(
            {"case_id": case_id, "trainee": trainee, "count": count}
        )
    return result


def recurring_issues(
    threads: list[dict[str, Any]],
    *,
    min_cases: int = 3,
    top_n: int = 10,
) -> list[dict[str, Any]]:
    """Group threads by normalized raised-body text across distinct cases."""
    groups: dict[str, dict[str, Any]] = {}
    for thread in threads:
        body = _thread_raised_body(thread)
        if not body.strip():
            continue
        key = _normalize_issue_text(body)
        if not key:
            continue
        bucket = groups.setdefault(
            key,
            {
                "normalized_text": key,
                "case_ids": set(),
                "thread_ids": [],
            },
        )
        case_id = str(thread.get("case_id") or "")
        if case_id:
            bucket["case_ids"].add(case_id)
        thread_id = str(thread.get("id") or "")
        if thread_id:
            bucket["thread_ids"].append(thread_id)

    ranked = [
        {
            "normalized_text": item["normalized_text"],
            "case_count": len(item["case_ids"]),
            "thread_ids": list(item["thread_ids"]),
        }
        for item in groups.values()
        if len(item["case_ids"]) >= min_cases
    ]
    ranked.sort(
        key=lambda row: (
            -row["case_count"],
            -len(row["thread_ids"]),
            row["normalized_text"],
        )
    )
    return ranked[:top_n]


def regression_rate(
    threads: list[dict[str, Any]],
    events: list[dict[str, Any]] | None = None,
) -> float:
    """Share of threads with a still_open event after a resolved event."""
    if not threads:
        return 0.0
    flat = _flatten_events(threads, events)
    by_thread: dict[str, list[dict[str, Any]]] = {}
    for event in flat:
        thread_id = str(event.get("thread_id") or "")
        if thread_id:
            by_thread.setdefault(thread_id, []).append(event)

    regressions = 0
    for thread in threads:
        thread_id = str(thread.get("id") or "")
        timeline = sorted(
            by_thread.get(thread_id, []),
            key=lambda event: str(event.get("created_at") or ""),
        )
        saw_resolved = False
        for event in timeline:
            event_type = str(event.get("event_type") or "")
            if event_type == "resolved":
                saw_resolved = True
            elif event_type == "still_open" and saw_resolved:
                regressions += 1
                break
    return regressions / len(threads)


def first_pass_rate_by_trainee(
    threads: list[dict[str, Any]],
    cases: list[dict[str, Any]],
) -> dict[str, float]:
    """Per trainee: share of cases that never had a correction thread."""
    cases_with_threads = {
        str(thread.get("case_id") or "")
        for thread in threads
        if thread.get("case_id")
    }
    by_trainee: dict[str, list[bool]] = {}
    for case in cases:
        trainee_id = str(case.get("trainee_id") or "")
        case_id = str(case.get("id") or case.get("case_id") or "")
        if not trainee_id or not case_id:
            continue
        by_trainee.setdefault(trainee_id, []).append(
            case_id not in cases_with_threads
        )
    return {
        trainee_id: (sum(flags) / len(flags) if flags else 0.0)
        for trainee_id, flags in by_trainee.items()
    }


def first_pass_trend(
    threads: list[dict[str, Any]],
    cases: list[dict[str, Any]],
    *,
    window: int = 10,
) -> dict[str, list[float]]:
    """First-pass rate over successive groups of `window` cases per trainee."""
    cases_with_threads = {
        str(thread.get("case_id") or "")
        for thread in threads
        if thread.get("case_id")
    }
    by_trainee: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        trainee_id = str(case.get("trainee_id") or "")
        if not trainee_id:
            continue
        by_trainee.setdefault(trainee_id, []).append(case)

    trends: dict[str, list[float]] = {}
    for trainee_id, trainee_cases in by_trainee.items():
        ordered = sorted(
            trainee_cases,
            key=lambda row: (
                str(row.get("approved_at") or row.get("assigned_at") or ""),
                int(row.get("set_no") or 0),
                int(row.get("case_no") or 0),
                str(row.get("id") or row.get("case_id") or ""),
            ),
        )
        rates: list[float] = []
        if window <= 0 or not ordered:
            trends[trainee_id] = rates
            continue
        for start_idx in range(0, len(ordered), window):
            chunk = ordered[start_idx : start_idx + window]
            first_pass = sum(
                1
                for case in chunk
                if str(case.get("id") or case.get("case_id") or "")
                not in cases_with_threads
            )
            rates.append(first_pass / len(chunk))
        trends[trainee_id] = rates
    return trends


def avg_days_per_case_by_trainee(
    cases: list[dict[str, Any]],
) -> dict[str, float | None]:
    """Mean assign→approve (or submit→approve) days per trainee."""

    def _days(start: Any, end: Any) -> float | None:
        if not start or not end:
            return None
        try:
            start_d = date.fromisoformat(str(start)[:10])
            end_d = date.fromisoformat(str(end)[:10])
        except ValueError:
            return None
        return float((end_d - start_d).days)

    by_trainee: dict[str, list[float]] = {}
    for case in cases:
        if str(case.get("status") or "") != "approved":
            continue
        trainee_id = str(case.get("trainee_id") or "")
        if not trainee_id:
            continue
        days = _days(case.get("assigned_at"), case.get("approved_at"))
        if days is None:
            days = _days(case.get("first_submitted_at"), case.get("approved_at"))
        if days is not None:
            by_trainee.setdefault(trainee_id, []).append(days)
    return {
        trainee_id: (round(mean(values), 1) if values else None)
        for trainee_id, values in by_trainee.items()
    }


def est_completion_by_trainee(
    cases: list[dict[str, Any]],
    revisions: list[dict[str, Any]] | None = None,
    *,
    today: date | None = None,
) -> dict[str, date | None]:
    """Per-trainee completion forecast using the same pace formula as blended."""
    del revisions  # Timestamps live on case metric rows today.
    today = today or date.today()
    by_trainee: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        trainee_id = str(case.get("trainee_id") or "")
        if trainee_id:
            by_trainee.setdefault(trainee_id, []).append(case)

    result: dict[str, date | None] = {}
    for trainee_id, trainee_cases in by_trainee.items():
        approved = [
            row
            for row in trainee_cases
            if str(row.get("status") or "") == "approved"
        ]
        remaining = len(trainee_cases) - len(approved)
        if remaining <= 0:
            result[trainee_id] = today
            continue
        durations: list[float] = []
        for row in approved:
            try:
                if row.get("assigned_at") and row.get("approved_at"):
                    start = date.fromisoformat(str(row["assigned_at"])[:10])
                    end = date.fromisoformat(str(row["approved_at"])[:10])
                    durations.append(float((end - start).days))
                elif row.get("first_submitted_at") and row.get("approved_at"):
                    start = date.fromisoformat(
                        str(row["first_submitted_at"])[:10]
                    )
                    end = date.fromisoformat(str(row["approved_at"])[:10])
                    durations.append(float((end - start).days))
            except ValueError:
                continue
        if not durations:
            result[trainee_id] = None
            continue
        result[trainee_id] = today + timedelta(
            days=round(mean(durations) * remaining)
        )
    return result


def regression_rate_by_trainee(
    threads: list[dict[str, Any]],
    cases: list[dict[str, Any]],
    events: list[dict[str, Any]] | None = None,
) -> dict[str, float]:
    """Regression rate scoped to each trainee's cases."""
    trainee_by_case = {
        str(case.get("id") or case.get("case_id") or ""): str(
            case.get("trainee_id") or ""
        )
        for case in cases
    }
    by_trainee: dict[str, list[dict[str, Any]]] = {}
    for thread in threads:
        case_id = str(thread.get("case_id") or "")
        trainee_id = trainee_by_case.get(case_id, "")
        if trainee_id:
            by_trainee.setdefault(trainee_id, []).append(thread)
    return {
        trainee_id: regression_rate(group, events)
        for trainee_id, group in by_trainee.items()
    }


def section_correction_rates(
    threads: list[dict[str, Any]],
    cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Per-section correction counts plus % of cohort cases touched."""
    total_cases = len(
        {
            str(case.get("id") or case.get("case_id") or "")
            for case in cases
            if case.get("id") or case.get("case_id")
        }
    )
    by_section: dict[str, set[str]] = {}
    open_by_section: dict[str, int] = {}
    for thread in threads:
        section = str(thread.get("section") or "")
        case_id = str(thread.get("case_id") or "")
        if not section:
            continue
        by_section.setdefault(section, set())
        if case_id:
            by_section[section].add(case_id)
        if thread.get("status") == "open":
            open_by_section[section] = open_by_section.get(section, 0) + 1

    rows: list[dict[str, Any]] = []
    for key, _label, _order in REVIEW_SECTIONS:
        case_ids = by_section.get(key, set())
        count = sum(
            1 for thread in threads if str(thread.get("section") or "") == key
        )
        rate = (len(case_ids) / total_cases) if total_cases else 0.0
        rows.append(
            {
                "section_key": key,
                "correction_count": count,
                "open_count": open_by_section.get(key, 0),
                "case_count": len(case_ids),
                "case_share": rate,
            }
        )
    rows.sort(key=lambda row: (-row["correction_count"], row["section_key"]))
    return rows
