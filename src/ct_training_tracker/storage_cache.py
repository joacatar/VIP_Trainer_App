"""Session-scoped caches to avoid re-downloading Storage on every Streamlit rerun."""

from __future__ import annotations

from typing import Any

import streamlit as st

from ct_training_tracker.repository import TrainingRepository

_STORAGE_CACHE_KEY = "_storage_bytes_cache"


def cached_storage_bytes(
    repository: TrainingRepository,
    storage_path: str,
) -> bytes:
    """Return Storage object bytes, reusing the current browser session cache."""
    cache: dict[str, bytes] = st.session_state.setdefault(_STORAGE_CACHE_KEY, {})
    if storage_path not in cache:
        cache[storage_path] = repository.download_storage_bytes(storage_path)
    return cache[storage_path]


def clear_storage_cache(session: Any | None = None) -> None:
    target = session if session is not None else st.session_state
    target.pop(_STORAGE_CACHE_KEY, None)
