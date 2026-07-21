import datetime as dt
from types import SimpleNamespace
from typing import Any

from ct_training_tracker.repository import TrainingRepository


class EmptyQuery:
    def select(self, *_args: Any) -> "EmptyQuery":
        return self

    def eq(self, *_args: Any) -> "EmptyQuery":
        return self

    def maybe_single(self) -> "EmptyQuery":
        return self

    def execute(self) -> None:
        return None


class EmptyClient:
    def table(self, _name: str) -> EmptyQuery:
        return EmptyQuery()


class RpcClient:
    def __init__(self) -> None:
        self.name = ""
        self.params: dict[str, Any] = {}

    def rpc(self, name: str, params: dict[str, Any]) -> "RpcClient":
        self.name = name
        self.params = params
        return self

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data="assignment-id")


def test_single_record_queries_handle_empty_supabase_response() -> None:
    repository = TrainingRepository(EmptyClient())  # type: ignore[arg-type]

    assert repository.get_profile("missing-user") is None
    assert repository.get_trainee_for_user("missing-user") is None


def test_assign_homework_uses_transactional_rpc() -> None:
    client = RpcClient()
    repository = TrainingRepository(client)  # type: ignore[arg-type]

    assignment_id = repository.assign_homework(
        case_id="case-id",
        title="Set 1 · Case 1",
        instructions="Complete all three files.",
        schedule_due_date=dt.date(2026, 7, 27),
        due_date=dt.date(2026, 7, 28),
    )

    assert assignment_id == "assignment-id"
    assert client.name == "assign_homework"
    assert client.params["scheduled_due"] == "2026-07-27"
    assert client.params["assigned_due"] == "2026-07-28"
