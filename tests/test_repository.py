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
    assert repository.get_revision_section("missing-section") is None


class SectionQuery:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def select(self, *_args: Any) -> "SectionQuery":
        return self

    def eq(self, *_args: Any) -> "SectionQuery":
        return self

    def maybe_single(self) -> "SectionQuery":
        return self

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=self._data)


class SectionClient:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def table(self, _name: str) -> SectionQuery:
        return SectionQuery(self._data)


def test_get_revision_section_sorts_corrections_and_screenshots() -> None:
    client = SectionClient(
        {
            "id": "section-1",
            "section_key": "scan",
            "corrections": [
                {
                    "id": "corr-2",
                    "created_at": "2026-01-02T00:00:00Z",
                    "correction_screenshots": [
                        {"id": "shot-2", "created_at": "2026-01-02T00:00:00Z"},
                        {"id": "shot-1", "created_at": "2026-01-01T00:00:00Z"},
                    ],
                },
                {
                    "id": "corr-1",
                    "created_at": "2026-01-01T00:00:00Z",
                    "correction_screenshots": [],
                },
            ],
        }
    )
    repository = TrainingRepository(client)  # type: ignore[arg-type]

    section = repository.get_revision_section("section-1")

    assert section is not None
    assert [row["id"] for row in section["corrections"]] == ["corr-1", "corr-2"]
    shots = section["corrections"][1]["correction_screenshots"]
    assert [row["id"] for row in shots] == ["shot-1", "shot-2"]


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
