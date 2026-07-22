from dataclasses import dataclass
from typing import Any, Literal

CaseOwner = Literal["trainee", "trainer", "none"]
AppRole = Literal["trainee", "trainer"]

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
