from typing import Literal, TypedDict


class Profile(TypedDict):
    id: str
    role: Literal["trainer", "trainee"]
    full_name: str


class Trainee(TypedDict):
    id: str
    full_name: str
    current_phase: str
    start_date: str
    is_test: bool


class HomeworkCase(TypedDict):
    set_no: int
    case_no: int
    catalog_label: str
    order_number: str


class CorrectionThread(TypedDict):
    id: str
    case_id: str
    section: str
    status: Literal["open", "resolved"]
    created_at: str
    resolved_at: str | None
    resolved_in_revision_id: str | None


class CorrectionEvent(TypedDict):
    id: str
    thread_id: str
    revision_id: str | None
    event_type: Literal["raised", "still_open", "resolved", "note"]
    body: str | None
    created_at: str


class HomeworkAssignment(TypedDict):
    id: str
    case_id: str
    title: str
    instructions: str | None
    status: str
    schedule_due_date: str
    due_date: str
    estimated_due_date: str | None
    cases: HomeworkCase
