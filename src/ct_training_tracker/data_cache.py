"""Session-scoped caches for trainer case/trainee lookups.

Streamlit reruns the whole page script on every interaction. Without this,
switching between cases in the inbox re-fetches every trainee's full case
list (with nested file requirements) and homework assignments on every
single click, which is the main cause of "changing case 1A to 2A is slow".

These helpers cache that data in `st.session_state` for the life of the
browser session. They are:

- Invalidated immediately by `invalidate_trainer_cache()` right after an
  action that actually changes trainee/case/file/homework data (assign,
  submit, review, publish, approve, create trainee).
- Backed by a short TTL as a safety net for changes made from a *different*
  session (e.g. the trainee submitting a package while the trainer already
  has this page open) — a page left open for a while will self-heal without
  requiring a manual refresh.

Ordinary navigation between cases/tabs within the same trainee reuses the
cache and does not touch the network at all.
"""

from __future__ import annotations

import time
from typing import Any

import streamlit as st

from ct_training_tracker.repository import TrainingRepository

_TTL_SECONDS = 45

_TRAINEES_KEY = "_cache_active_trainees"
_CASES_PREFIX = "_cache_trainee_cases_"
_HOMEWORK_PREFIX = "_cache_case_homework_"


def _get(key: str) -> Any | None:
    entry = st.session_state.get(key)
    if entry is None:
        return None
    fetched_at, value = entry
    if time.monotonic() - fetched_at > _TTL_SECONDS:
        return None
    return value


def _set(key: str, value: Any) -> None:
    st.session_state[key] = (time.monotonic(), value)


def cached_active_trainees(repository: TrainingRepository) -> list[dict[str, Any]]:
    cached = _get(_TRAINEES_KEY)
    if cached is not None:
        return cached
    rows = [dict(row) for row in repository.list_active_trainees()]
    _set(_TRAINEES_KEY, rows)
    return rows


def cached_trainee_cases(
    repository: TrainingRepository,
    trainee_id: str,
    *,
    include_files: bool = False,
) -> list[dict[str, Any]]:
    key = f"{_CASES_PREFIX}{trainee_id}_{include_files}"
    cached = _get(key)
    if cached is not None:
        return cached
    rows = repository.list_cases(trainee_id, include_files=include_files)
    _set(key, rows)
    return rows


def cached_homework_for_cases(
    repository: TrainingRepository,
    case_ids: list[str],
) -> list[dict[str, Any]]:
    if not case_ids:
        return []
    key = f"{_HOMEWORK_PREFIX}{'_'.join(sorted(case_ids))}"
    cached = _get(key)
    if cached is not None:
        return cached
    rows = repository.list_homework_for_cases(case_ids)
    _set(key, rows)
    return rows


def invalidate_trainer_cache(trainee_id: str | None = None) -> None:
    """Drop cached trainer lookups after a mutation.

    A full clear is simplest and always correct: the next time any trainer
    view needs this data it will be fetched fresh. `trainee_id` is accepted
    for call-site clarity even though the current implementation clears
    everything — cheap to clear, and avoids subtly stale caches for other
    trainees sharing an unrelated key prefix.
    """
    del trainee_id
    prefixes = (_TRAINEES_KEY, _CASES_PREFIX, _HOMEWORK_PREFIX)
    for key in [k for k in st.session_state if k.startswith(prefixes)]:
        del st.session_state[key]
