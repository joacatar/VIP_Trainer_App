from typing import Any

import ct_training_tracker.data_cache as data_cache


class _FakeRepository:
    def __init__(self) -> None:
        self.trainee_calls = 0
        self.case_calls = 0
        self.homework_calls = 0

    def list_active_trainees(self) -> list[dict[str, Any]]:
        self.trainee_calls += 1
        return [{"id": "t1", "full_name": "Trainee One"}]

    def list_cases(
        self, trainee_id: str, *, include_files: bool = False
    ) -> list[dict[str, Any]]:
        self.case_calls += 1
        return [{"id": "case-1", "trainee_id": trainee_id}]

    def list_homework_for_cases(self, case_ids: list[str]) -> list[dict[str, Any]]:
        self.homework_calls += 1
        return [{"case_id": case_id} for case_id in case_ids]


def test_cached_active_trainees_reuses_session_state(monkeypatch) -> None:
    monkeypatch.setattr(data_cache.st, "session_state", {})
    repository = _FakeRepository()

    first = data_cache.cached_active_trainees(repository)
    second = data_cache.cached_active_trainees(repository)

    assert first == second
    assert repository.trainee_calls == 1


def test_cached_trainee_cases_and_homework_reuse_cache(monkeypatch) -> None:
    monkeypatch.setattr(data_cache.st, "session_state", {})
    repository = _FakeRepository()

    cases = data_cache.cached_trainee_cases(repository, "t1", include_files=True)
    data_cache.cached_trainee_cases(repository, "t1", include_files=True)
    data_cache.cached_homework_for_cases(repository, [row["id"] for row in cases])
    data_cache.cached_homework_for_cases(repository, [row["id"] for row in cases])

    assert repository.case_calls == 1
    assert repository.homework_calls == 1


def test_cache_expires_after_ttl(monkeypatch) -> None:
    monkeypatch.setattr(data_cache.st, "session_state", {})
    repository = _FakeRepository()

    clock = {"now": 0.0}
    monkeypatch.setattr(data_cache.time, "monotonic", lambda: clock["now"])

    data_cache.cached_active_trainees(repository)
    clock["now"] += data_cache._TTL_SECONDS + 1
    data_cache.cached_active_trainees(repository)

    assert repository.trainee_calls == 2


def test_invalidate_trainer_cache_clears_everything(monkeypatch) -> None:
    state: dict[str, Any] = {}
    monkeypatch.setattr(data_cache.st, "session_state", state)
    repository = _FakeRepository()

    data_cache.cached_active_trainees(repository)
    cases = data_cache.cached_trainee_cases(repository, "t1", include_files=True)
    data_cache.cached_homework_for_cases(repository, [row["id"] for row in cases])
    assert state

    data_cache.invalidate_trainer_cache()
    assert state == {}

    data_cache.cached_active_trainees(repository)
    assert repository.trainee_calls == 2
