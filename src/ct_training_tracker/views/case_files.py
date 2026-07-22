"""Case file upload and review widgets."""

from __future__ import annotations

from typing import Any

import streamlit as st
from postgrest.exceptions import APIError

from ct_training_tracker.files import ALLOWED_EXTENSIONS, FILE_KIND_LABELS
from ct_training_tracker.metrics import file_slot_label
from ct_training_tracker.repository import TrainingRepository

UPLOADABLE_STATUSES = {"assigned", "submitted", "awaiting_resubmission", "in_review"}
KIND_ORDER = ("pdf_primary", "pdf_secondary", "ov")


def _sorted_requirements(requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order = {kind: index for index, kind in enumerate(KIND_ORDER)}
    return sorted(requirements, key=lambda row: order.get(row["kind"], 99))


def _uploader_type(kind: str) -> list[str] | None:
    """Browser accept filters break on obscure compound extensions.

    Keep the filter for PDFs; leave OV unrestricted and validate in Python.
    """
    if kind.startswith("pdf"):
        return ["pdf"]
    return None


def _feedback_key(requirement_id: str) -> str:
    return f"upload_feedback_{requirement_id}"


def _show_feedback(requirement_id: str) -> None:
    feedback = st.session_state.get(_feedback_key(requirement_id))
    if not feedback:
        return
    level, message = feedback
    if level == "success":
        st.success(message)
    elif level == "error":
        st.error(message)
    else:
        st.info(message)


def _set_feedback(requirement_id: str, level: str, message: str) -> None:
    st.session_state[_feedback_key(requirement_id)] = (level, message)


def render_trainee_case_uploads(
    repository: TrainingRepository,
    *,
    user_id: str,
    case: dict[str, Any],
) -> None:
    if case["status"] not in UPLOADABLE_STATUSES:
        st.caption(
            f"This case is not ready for uploads yet "
            f"(status: {str(case['status']).replace('_', ' ')})."
        )
        return

    requirements = _sorted_requirements(
        repository.list_requirements_for_case(case["id"])
    )
    for requirement in requirements:
        label = FILE_KIND_LABELS[requirement["kind"]]
        slot_state = file_slot_label(requirement["status"])
        latest = requirement.get("latest_file")
        allowed = ALLOWED_EXTENSIONS.get(requirement["kind"], ())
        requirement_id = requirement["id"]

        with st.container(border=True):
            st.markdown(f"**{label}** · {slot_state}")
            _show_feedback(requirement_id)
            if requirement.get("replacement_reason"):
                st.warning(requirement["replacement_reason"])
            if latest:
                st.caption(
                    f"Latest: {latest['original_filename']} (v{latest['version_no']})"
                )
            if requirement["status"] == "accepted":
                st.success("Accepted — nothing else to send for this slot.")
                continue

            if requirement["status"] in {"submitted", "under_review"}:
                st.success("Sent — waiting for trainer review.")
                continue

            if allowed:
                st.caption(
                    f"Required extension: {', '.join(allowed)}. "
                    "Max size: 1 GB per file."
                )

            # Do not put file_uploader inside st.form — Streamlit often returns
            # None on submit even when a file was selected.
            uploaded = st.file_uploader(
                f"Choose {label}",
                type=_uploader_type(requirement["kind"]),
                key=f"upload_{requirement_id}",
            )
            if uploaded is not None:
                st.info(
                    f"Selected `{uploaded.name}` · {uploaded.size:,} bytes · "
                    f"mime `{uploaded.type or 'unknown'}`"
                )

            submit = st.button(
                f"Submit {label}",
                key=f"submit_{requirement_id}",
                type="primary",
                disabled=uploaded is None,
            )
            if not submit:
                continue
            if uploaded is None:
                _set_feedback(
                    requirement_id,
                    "error",
                    f"No file selected for {label}. Choose a file, then submit.",
                )
                st.rerun()

            with st.spinner(f"Uploading {uploaded.name}…"):
                try:
                    repository.upload_case_file(
                        user_id=user_id,
                        case_id=case["id"],
                        requirement_id=requirement_id,
                        kind=requirement["kind"],
                        filename=uploaded.name,
                        content=uploaded.getvalue(),
                        mime_type=uploaded.type or "application/octet-stream",
                    )
                except (APIError, ValueError, Exception) as exc:
                    message = getattr(exc, "message", None) or str(exc)
                    _set_feedback(
                        requirement_id,
                        "error",
                        f"Upload failed for `{uploaded.name}`: {message}",
                    )
                    st.rerun()

            _set_feedback(
                requirement_id,
                "success",
                f"{label} uploaded: `{uploaded.name}`",
            )
            st.rerun()


def render_trainer_case_review(
    repository: TrainingRepository,
    *,
    case: dict[str, Any],
) -> None:
    if case["status"] not in {
        "submitted",
        "in_review",
        "awaiting_resubmission",
        "assigned",
    }:
        st.caption("Assign this case before reviewing files.")
        return

    requirements = _sorted_requirements(
        repository.list_requirements_for_case(case["id"])
    )
    for requirement in requirements:
        label = FILE_KIND_LABELS[requirement["kind"]]
        slot_state = file_slot_label(requirement["status"])
        latest = requirement.get("latest_file")
        with st.container(border=True):
            st.markdown(f"**{label}** · {slot_state}")
            if not latest:
                st.caption("Not sent yet.")
                continue

            st.caption(
                f"{latest['original_filename']} · version {latest['version_no']}"
            )
            try:
                download_url = repository.create_signed_download_url(
                    latest["storage_path"]
                )
                st.link_button("Download", download_url)
            except Exception as exc:
                st.error(f"Download unavailable: {exc}")

            if requirement["status"] == "accepted":
                st.success("Already accepted.")
                continue

            note = st.text_input(
                "Review note",
                key=f"review_note_{requirement['id']}",
                placeholder="Optional note for replacement requests",
            )
            accept_col, reject_col = st.columns(2)
            if accept_col.button(
                f"Accept {label}",
                key=f"accept_{requirement['id']}",
            ):
                try:
                    repository.review_case_file(
                        file_id=latest["id"],
                        decision="accepted",
                        note=note,
                    )
                except APIError as exc:
                    st.error(exc.message)
                    continue
                st.success(f"{label} accepted.")
                st.rerun()
            if reject_col.button(
                "Request replacement",
                key=f"reject_{requirement['id']}",
            ):
                try:
                    repository.review_case_file(
                        file_id=latest["id"],
                        decision="rejected",
                        note=note,
                    )
                except APIError as exc:
                    st.error(exc.message)
                    continue
                st.warning(f"{label} marked for replacement.")
                st.rerun()
