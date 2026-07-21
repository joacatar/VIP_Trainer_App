"""Case file upload and review widgets."""

from __future__ import annotations

from typing import Any

import streamlit as st
from postgrest.exceptions import APIError

from ct_training_tracker.files import FILE_KIND_LABELS
from ct_training_tracker.repository import TrainingRepository

UPLOADABLE_STATUSES = {"assigned", "submitted", "awaiting_resubmission", "in_review"}
KIND_ORDER = ("pdf_primary", "pdf_secondary", "ov")


def _sorted_requirements(requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order = {kind: index for index, kind in enumerate(KIND_ORDER)}
    return sorted(requirements, key=lambda row: order.get(row["kind"], 99))


def render_trainee_case_uploads(
    repository: TrainingRepository,
    *,
    user_id: str,
    case: dict[str, Any],
) -> None:
    if case["status"] not in UPLOADABLE_STATUSES:
        st.caption("This case is not ready for uploads yet.")
        return

    requirements = _sorted_requirements(
        repository.list_requirements_for_case(case["id"])
    )
    for requirement in requirements:
        label = FILE_KIND_LABELS[requirement["kind"]]
        status = str(requirement["status"]).replace("_", " ").title()
        latest = requirement.get("latest_file")
        with st.container(border=True):
            st.markdown(f"**{label}** · {status}")
            if requirement.get("replacement_reason"):
                st.warning(requirement["replacement_reason"])
            if latest:
                st.caption(
                    f"Latest: {latest['original_filename']} (v{latest['version_no']})"
                )
            if requirement["status"] == "accepted":
                st.success("Accepted — no re-upload needed.")
                continue

            uploaded = st.file_uploader(
                f"Upload {label}",
                type=["pdf"] if requirement["kind"].startswith("pdf") else ["ov"],
                key=f"upload_{requirement['id']}",
            )
            if uploaded is None:
                continue
            if st.button(f"Submit {label}", key=f"submit_{requirement['id']}"):
                try:
                    repository.upload_case_file(
                        user_id=user_id,
                        case_id=case["id"],
                        requirement_id=requirement["id"],
                        kind=requirement["kind"],
                        filename=uploaded.name,
                        content=uploaded.getvalue(),
                        mime_type=uploaded.type,
                    )
                except (APIError, ValueError, Exception) as exc:
                    message = getattr(exc, "message", str(exc))
                    st.error(f"Upload failed: {message}")
                    continue
                st.success(f"{label} submitted.")
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
        status = str(requirement["status"]).replace("_", " ").title()
        latest = requirement.get("latest_file")
        with st.container(border=True):
            st.markdown(f"**{label}** · {status}")
            if not latest:
                st.caption("No file uploaded yet.")
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
