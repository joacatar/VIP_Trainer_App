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


class RecordingQuery:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self._data = data
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def select(self, *args: Any) -> "RecordingQuery":
        self.calls.append(("select", args))
        return self

    def eq(self, *args: Any) -> "RecordingQuery":
        self.calls.append(("eq", args))
        return self

    def order(self, *args: Any, **_kwargs: Any) -> "RecordingQuery":
        self.calls.append(("order", args))
        return self

    def limit(self, *args: Any) -> "RecordingQuery":
        self.calls.append(("limit", args))
        return self

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=self._data)


class RecordingClient:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.query = RecordingQuery(data)

    def table(self, _name: str) -> RecordingQuery:
        return self.query


def test_list_questions_for_trainee_filters_by_trainee_and_sorts_screenshots() -> None:
    data = [
        {
            "id": "q1",
            "case_id": "case-1",
            "question_screenshots": [
                {"id": "s2", "created_at": "2026-01-02"},
                {"id": "s1", "created_at": "2026-01-01"},
            ],
        }
    ]
    client = RecordingClient(data)
    repository = TrainingRepository(client)  # type: ignore[arg-type]

    rows = repository.list_questions_for_trainee("trainee-1")

    assert rows[0]["id"] == "q1"
    assert [row["id"] for row in rows[0]["question_screenshots"]] == ["s1", "s2"]
    assert ("eq", ("cases.trainee_id", "trainee-1")) in client.query.calls


def test_mark_question_viewed_calls_rpc_with_question_id() -> None:
    client = RpcClient()
    repository = TrainingRepository(client)  # type: ignore[arg-type]

    repository.mark_question_viewed("question-1")

    assert client.name == "mark_question_viewed"
    assert client.params == {"target_question_id": "question-1"}


def test_count_unread_answers_for_trainee_returns_rpc_result() -> None:
    class CountRpcClient:
        def rpc(self, name: str, params: dict[str, Any]) -> "CountRpcClient":
            self.name = name
            self.params = params
            return self

        def execute(self) -> SimpleNamespace:
            return SimpleNamespace(data=3)

    client = CountRpcClient()
    repository = TrainingRepository(client)  # type: ignore[arg-type]

    assert repository.count_unread_answers_for_trainee("trainee-1") == 3
    assert client.name == "count_unread_question_answers"
    assert client.params == {"target_trainee_id": "trainee-1"}
