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


class OrderRecordingQuery(RecordingQuery):
    def __init__(self, data: list[dict[str, Any]]) -> None:
        super().__init__(data)
        self.order_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def order(self, *args: Any, **kwargs: Any) -> "OrderRecordingQuery":
        self.order_calls.append((args, kwargs))
        return self


def test_list_revisions_for_case_orders_newest_first() -> None:
    class OrderRecordingClient:
        def __init__(self) -> None:
            self.query = OrderRecordingQuery([])

        def table(self, _name: str) -> OrderRecordingQuery:
            return self.query

    client = OrderRecordingClient()
    repository = TrainingRepository(client)  # type: ignore[arg-type]

    repository.list_revisions_for_case("case-1")

    assert ("eq", ("case_id", "case-1")) in client.query.calls
    assert client.query.order_calls == [(("revision_no",), {"desc": True})]


def test_create_correction_thread_uses_atomic_rpc() -> None:
    client = RpcClient()
    repository = TrainingRepository(client)  # type: ignore[arg-type]

    thread_id = repository.create_correction_thread(
        case_id="case-1",
        section="scan",
        body="Fix the scan orientation.",
        revision_id="rev-1",
    )

    assert thread_id == "assignment-id"
    assert client.name == "create_correction_thread"
    assert client.params == {
        "target_case_id": "case-1",
        "target_section": "scan",
        "thread_body": "Fix the scan orientation.",
        "target_revision_id": "rev-1",
        "target_related_file": None,
    }


def test_resolve_and_reopen_thread_call_rpcs() -> None:
    client = RpcClient()
    repository = TrainingRepository(client)  # type: ignore[arg-type]

    repository.resolve_thread("thread-1", "rev-2")
    assert client.name == "resolve_correction_thread"
    assert client.params == {
        "target_thread_id": "thread-1",
        "target_revision_id": "rev-2",
    }

    repository.reopen_thread("thread-1", "rev-3")
    assert client.name == "reopen_correction_thread"
    assert client.params == {
        "target_thread_id": "thread-1",
        "target_revision_id": "rev-3",
    }


def test_mark_open_threads_still_open_returns_stamped_count() -> None:
    class CountRpcClient:
        def rpc(self, name: str, params: dict[str, Any]) -> "CountRpcClient":
            self.name = name
            self.params = params
            return self

        def execute(self) -> SimpleNamespace:
            return SimpleNamespace(data=2)

    client = CountRpcClient()
    repository = TrainingRepository(client)  # type: ignore[arg-type]

    stamped = repository.mark_open_threads_still_open(
        case_id="case-1",
        revision_id="rev-4",
    )

    assert stamped == 2
    assert client.name == "mark_open_threads_still_open"
    assert client.params == {
        "target_case_id": "case-1",
        "target_revision_id": "rev-4",
    }


def test_add_correction_event_inserts_row() -> None:
    class InsertQuery:
        def __init__(self) -> None:
            self.inserted: dict[str, Any] | None = None

        def insert(self, payload: dict[str, Any]) -> "InsertQuery":
            self.inserted = payload
            return self

        def execute(self) -> SimpleNamespace:
            return SimpleNamespace(data=[])

    class InsertClient:
        def __init__(self) -> None:
            self.query = InsertQuery()
            self.table_name = ""

        def table(self, name: str) -> InsertQuery:
            self.table_name = name
            return self.query

    client = InsertClient()
    repository = TrainingRepository(client)  # type: ignore[arg-type]

    repository.add_correction_event(
        thread_id="thread-1",
        revision_id="rev-1",
        event_type="note",
        body="Discussed on the call.",
    )

    assert client.table_name == "correction_events"
    assert client.query.inserted == {
        "thread_id": "thread-1",
        "revision_id": "rev-1",
        "event_type": "note",
        "body": "Discussed on the call.",
    }


class CrudQuery:
    def __init__(self) -> None:
        self.inserted: Any = None
        self.updated: dict[str, Any] | None = None
        self.deleted = False
        self.filters: list[tuple[str, Any]] = []

    def select(self, *_args: Any) -> "CrudQuery":
        return self

    def insert(self, payload: Any) -> "CrudQuery":
        self.inserted = payload
        return self

    def update(self, payload: dict[str, Any]) -> "CrudQuery":
        self.updated = payload
        return self

    def delete(self) -> "CrudQuery":
        self.deleted = True
        return self

    def eq(self, column: str, value: Any) -> "CrudQuery":
        self.filters.append((column, value))
        return self

    def order(self, *_args: Any, **_kwargs: Any) -> "CrudQuery":
        return self

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=[{"id": "resource-1"}])


class CrudClient:
    def __init__(self) -> None:
        self.query = CrudQuery()
        self.table_name = ""

    def table(self, name: str) -> CrudQuery:
        self.table_name = name
        return self.query


def test_add_case_resource_inserts_row_and_returns_id() -> None:
    client = CrudClient()
    repository = TrainingRepository(client)  # type: ignore[arg-type]

    resource_id = repository.add_case_resource(
        case_id="case-1",
        resource_type="link",
        title="Getting started guide",
        url="https://example.com/guide",
    )

    assert resource_id == "resource-1"
    assert client.table_name == "case_resources"
    assert client.query.inserted == {
        "case_id": "case-1",
        "resource_type": "link",
        "title": "Getting started guide",
        "url": "https://example.com/guide",
        "body": None,
        "created_by": "trainer",
        "sort_order": 0,
    }


def test_update_case_resource_patches_only_given_fields() -> None:
    client = CrudClient()
    repository = TrainingRepository(client)  # type: ignore[arg-type]

    repository.update_case_resource("resource-1", title="New title")

    assert client.query.updated == {"title": "New title"}
    assert ("id", "resource-1") in client.query.filters


def test_delete_case_resource_deletes_by_id() -> None:
    client = CrudClient()
    repository = TrainingRepository(client)  # type: ignore[arg-type]

    repository.delete_case_resource("resource-1")

    assert client.query.deleted is True
    assert ("id", "resource-1") in client.query.filters


def test_list_case_resources_filters_by_case() -> None:
    client = CrudClient()
    repository = TrainingRepository(client)  # type: ignore[arg-type]

    rows = repository.list_case_resources("case-1")

    assert rows == [{"id": "resource-1"}]
    assert ("case_id", "case-1") in client.query.filters


def test_add_case_resources_bulk_skips_empty_list() -> None:
    client = CrudClient()
    repository = TrainingRepository(client)  # type: ignore[arg-type]

    repository.add_case_resources([])
    assert client.query.inserted is None

    repository.add_case_resources([{"case_id": "case-1"}])
    assert client.query.inserted == [{"case_id": "case-1"}]


def test_list_correction_threads_filters_and_sorts_events() -> None:
    data = [
        {
            "id": "t1",
            "correction_events": [
                {"id": "e2", "created_at": "2026-01-02"},
                {"id": "e1", "created_at": "2026-01-01"},
            ],
            "correction_thread_screenshots": [
                {"id": "s2", "created_at": "2026-01-02"},
                {"id": "s1", "created_at": "2026-01-01"},
            ],
        }
    ]
    client = RecordingClient(data)
    repository = TrainingRepository(client)  # type: ignore[arg-type]

    threads = repository.list_correction_threads("case-1", status="open")

    assert ("eq", ("case_id", "case-1")) in client.query.calls
    assert ("eq", ("status", "open")) in client.query.calls
    events = threads[0]["correction_events"]
    assert [event["id"] for event in events] == ["e1", "e2"]
    shots = threads[0]["correction_thread_screenshots"]
    assert [shot["id"] for shot in shots] == ["s1", "s2"]


class BulkDueQuery:
    def __init__(self, client: "BulkDueClient", table_name: str) -> None:
        self._client = client
        self._table = table_name
        self._payload: dict[str, Any] | None = None
        self._case_id: str | None = None

    def update(self, payload: dict[str, Any]) -> "BulkDueQuery":
        self._payload = payload
        return self

    def eq(self, column: str, value: Any) -> "BulkDueQuery":
        if column == "id" or column == "case_id":
            self._case_id = str(value)
        return self

    def execute(self) -> SimpleNamespace:
        assert self._payload is not None
        assert self._case_id is not None
        if self._table == "cases" and self._case_id in self._client.fail_on_cases:
            raise RuntimeError(f"failed {self._case_id}")
        self._client.calls.append((self._table, self._case_id, dict(self._payload)))
        return SimpleNamespace(data=[])


class BulkDueClient:
    def __init__(self, fail_on_cases: set[str] | None = None) -> None:
        self.fail_on_cases = fail_on_cases or set()
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def table(self, name: str) -> BulkDueQuery:
        return BulkDueQuery(self, name)


def test_bulk_update_due_dates_updates_cases_and_homework() -> None:
    client = BulkDueClient()
    repository = TrainingRepository(client)  # type: ignore[arg-type]

    failed = repository.bulk_update_due_dates(
        [
            ("case-a", dt.date(2026, 8, 10)),
            ("case-b", dt.date(2026, 8, 11)),
        ]
    )

    assert failed == []
    assert client.calls == [
        ("cases", "case-a", {"due_date": "2026-08-10"}),
        ("homework_assignments", "case-a", {"due_date": "2026-08-10"}),
        ("cases", "case-b", {"due_date": "2026-08-11"}),
        ("homework_assignments", "case-b", {"due_date": "2026-08-11"}),
    ]


def test_bulk_update_due_dates_reports_partial_failures() -> None:
    client = BulkDueClient(fail_on_cases={"case-b"})
    repository = TrainingRepository(client)  # type: ignore[arg-type]

    failed = repository.bulk_update_due_dates(
        [
            ("case-a", dt.date(2026, 8, 10)),
            ("case-b", dt.date(2026, 8, 11)),
            ("case-c", dt.date(2026, 8, 12)),
        ]
    )

    assert failed == ["case-b"]
    updated_cases = [case_id for table, case_id, _ in client.calls if table == "cases"]
    assert updated_cases == ["case-a", "case-c"]


class RecordingCaseQuery:
    """Captures the filters and ordering list_cases applies."""

    def __init__(self, log: dict[str, Any]) -> None:
        self._log = log

    def select(self, columns: str) -> "RecordingCaseQuery":
        self._log["columns"] = columns
        return self

    def eq(self, column: str, value: Any) -> "RecordingCaseQuery":
        self._log.setdefault("eq", []).append((column, value))
        return self

    def lte(self, column: str, value: Any) -> "RecordingCaseQuery":
        self._log.setdefault("lte", []).append((column, value))
        return self

    def order(self, column: str) -> "RecordingCaseQuery":
        self._log.setdefault("order", []).append(column)
        return self

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=[])


class RecordingCaseClient:
    def __init__(self) -> None:
        self.log: dict[str, Any] = {}

    def table(self, name: str) -> RecordingCaseQuery:
        self.log["table"] = name
        return RecordingCaseQuery(self.log)


def test_list_cases_defaults_to_every_phase_and_release_state() -> None:
    client = RecordingCaseClient()
    repository = TrainingRepository(client)  # type: ignore[arg-type]

    repository.list_cases("trainee-1")

    assert client.log["eq"] == [("trainee_id", "trainee-1")]
    assert "lte" not in client.log
    assert client.log["order"] == ["phase_no", "set_no", "case_no"]
    assert "phase_no" in client.log["columns"]
    assert "released_on" in client.log["columns"]


def test_list_cases_can_limit_to_one_phase() -> None:
    client = RecordingCaseClient()
    repository = TrainingRepository(client)  # type: ignore[arg-type]

    repository.list_cases("trainee-1", phase_no=2)

    assert ("phase_no", 2) in client.log["eq"]


def test_list_cases_hides_unreleased_phase_2_cases_when_asked() -> None:
    client = RecordingCaseClient()
    repository = TrainingRepository(client)  # type: ignore[arg-type]

    repository.list_cases("trainee-1", phase_no=2, released_only=True)

    assert client.log["lte"] == [
        ("released_on", dt.date.today().isoformat())
    ]


def test_phase_2_cases_never_borrow_a_phase_1_vip_order_number() -> None:
    from ct_training_tracker.case_labels import (
        case_catalog_label,
        case_order_number,
        case_title,
    )

    # Phase 2 reuses set_no 1 with case_no 1-30; case 3 of set 1 has a real
    # phase-1 order number that must not leak into the live case.
    phase_1 = {"phase_no": 1, "set_no": 1, "case_no": 3, "catalog_label": "3A"}
    phase_2 = {
        "phase_no": 2,
        "set_no": 1,
        "case_no": 3,
        "catalog_label": "L03",
        "order_number": None,
    }

    assert case_order_number(phase_1) == "12-26-02-0008"
    assert case_order_number(phase_2) is None
    assert case_title(phase_2) == "Live case L03"
    assert case_catalog_label(phase_2) == "L03"


def test_phase_2_case_shows_its_real_order_number_once_backfilled() -> None:
    from ct_training_tracker.case_labels import case_title

    case = {
        "phase_no": 2,
        "set_no": 1,
        "case_no": 3,
        "catalog_label": "L03",
        "order_number": "12-26-09-0123",
    }

    assert case_title(case) == "Live case L03 · 12-26-09-0123"


def test_rows_without_phase_no_still_behave_as_phase_1() -> None:
    from ct_training_tracker.case_labels import case_order_number

    legacy = {"set_no": 2, "case_no": 1, "catalog_label": "1B"}

    assert case_order_number(legacy) == "12-26-02-0003"


def test_case_columns_never_leak_the_source_case_by_default() -> None:
    client = RecordingCaseClient()
    repository = TrainingRepository(client)  # type: ignore[arg-type]

    repository.list_cases("trainee-1", phase_no=2, released_only=True)

    columns = client.log["columns"]
    assert "source_order_number" not in columns
    # The manual/plan-only instruction does have to reach the trainee.
    assert "instruction" in columns


def test_trainer_can_opt_into_the_source_case() -> None:
    client = RecordingCaseClient()
    repository = TrainingRepository(client)  # type: ignore[arg-type]

    repository.list_cases("trainee-1", phase_no=2, include_source=True)

    assert "source_order_number" in client.log["columns"]


def test_case_label_shows_live_case_for_phase_2() -> None:
    from ct_training_tracker.case_labels import case_label

    phase_1 = {"phase_no": 1, "set_no": 1, "case_no": 1, "catalog_label": "1A"}
    phase_2 = {
        "phase_no": 2,
        "set_no": 1,
        "case_no": 6,
        "catalog_label": "L06",
        "order_number": "12-26-07-0005",
    }

    assert case_label(phase_1) == "Case 1A · 12-26-02-0002"
    assert case_label(phase_2) == "Live case L06 · 12-26-07-0005"
