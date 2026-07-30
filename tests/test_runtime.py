from types import SimpleNamespace
from typing import Any

import ct_training_tracker.runtime as runtime


class _FakeAuth:
    def __init__(self, user_id: str = "user-1") -> None:
        self.calls = 0
        self._user_id = user_id

    def get_user(self) -> SimpleNamespace:
        self.calls += 1
        return SimpleNamespace(user=SimpleNamespace(id=self._user_id))


class _FakeClient:
    def __init__(self, user_id: str = "user-1") -> None:
        self.auth = _FakeAuth(user_id)


def _fake_profile(self: Any, user_id: str) -> dict[str, Any]:
    return {"id": user_id, "role": "trainer", "full_name": "Trainer"}


def test_load_profile_caches_by_access_token(monkeypatch) -> None:
    monkeypatch.setattr(runtime.st, "session_state", {"access_token": "token-a"})
    profile_calls = {"count": 0}

    def counting_profile(self: Any, user_id: str) -> dict[str, Any]:
        profile_calls["count"] += 1
        return _fake_profile(self, user_id)

    monkeypatch.setattr(runtime.TrainingRepository, "get_profile", counting_profile)
    client = _FakeClient()

    first = runtime.load_profile(client)
    second = runtime.load_profile(client)

    assert first == second
    assert client.auth.calls == 1
    assert profile_calls["count"] == 1


def test_load_profile_refetches_after_token_changes(monkeypatch) -> None:
    state = {"access_token": "token-a"}
    monkeypatch.setattr(runtime.st, "session_state", state)
    monkeypatch.setattr(runtime.TrainingRepository, "get_profile", _fake_profile)

    client = _FakeClient()
    runtime.load_profile(client)

    state["access_token"] = "token-b"
    other_client = _FakeClient()
    runtime.load_profile(other_client)

    assert other_client.auth.calls == 1


def test_create_client_or_none_reuses_cached_client_for_same_token(
    monkeypatch,
) -> None:
    monkeypatch.setattr(runtime.st, "session_state", {"access_token": "token-a"})
    monkeypatch.setattr(runtime, "_load_settings", lambda: object())
    created = {"count": 0}

    def fake_create_authenticated_client(settings: Any, session: Any) -> _FakeClient:
        created["count"] += 1
        return _FakeClient()

    monkeypatch.setattr(
        runtime, "create_authenticated_client", fake_create_authenticated_client
    )
    monkeypatch.setattr(runtime.TrainingRepository, "get_profile", _fake_profile)

    client_one = runtime.create_client_or_none()
    profile_one = runtime.load_profile(client_one)
    client_two = runtime.create_client_or_none()
    profile_two = runtime.load_profile(client_two)

    assert client_one is client_two
    assert profile_one == profile_two
    assert created["count"] == 1
