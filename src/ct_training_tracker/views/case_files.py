"""Case file link submission and review widgets (OneDrive links)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import streamlit as st
from postgrest.exceptions import APIError

from ct_training_tracker.files import FILE_KIND_LABELS
from ct_training_tracker.metrics import file_slot_label
from ct_training_tracker.repository import TrainingRepository

EDITABLE_CASE_STATUSES = {
    "assigned",
    "submitted",
    "awaiting_resubmission",
    "in_review",
    "corrections_sent",
}
KIND_ORDER = ("pdf_primary", "pdf_secondary", "ov")
SENT_STATUSES = {"submitted", "under_review"}


def _sorted_requirements(requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order = {kind: index for index, kind in enumerate(KIND_ORDER)}
    return sorted(requirements, key=lambda row: order.get(row["kind"], 99))


def _normalize_share_url(raw: str) -> str:
    value = raw.strip()
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Link must be a full http(s) URL (e.g. OneDrive share link).")
    return value


def render_trainee_case_uploads(
    repository: TrainingRepository,
    *,
    user_id: str,
    case: dict[str, Any],
) -> None:
    del user_id  # Auth comes from the session client / RPC.
    if case["status"] not in EDITABLE_CASE_STATUSES:
        st.caption(
            "This case is not ready for file links yet "
            f"(status: {str(case['status']).replace('_', ' ')})."
        )
        return

    requirements = _sorted_requirements(
        repository.list_requirements_for_case(case["id"])
    )
    for requirement in requirements:
        label = FILE_KIND_LABELS[requirement["kind"]]
        slot_state = file_slot_label(requirement["status"])
        requirement_id = requirement["id"]
        current_url = requirement.get("external_url") or ""

        with st.container(border=True):
            st.markdown(f"**{label}** · {slot_state}")
            if requirement.get("replacement_reason"):
                st.warning(requirement["replacement_reason"])

            if requirement["status"] == "accepted":
                if current_url:
                    st.link_button("Open OneDrive link", current_url)
                st.success("Accepted — nothing else to send for this slot.")
                continue

            st.caption("Paste a OneDrive share link, then mark as sent.")
            url_value = st.text_input(
                f"{label} OneDrive link",
                value=current_url,
                key=f"link_{requirement_id}",
                placeholder="https://…onedrive…/…",
            )

            if requirement["status"] in SENT_STATUSES:
                st.success("Sent — waiting for trainer review.")
                if current_url:
                    st.link_button("Open current link", current_url)
                if st.button(
                    f"Undo sent · {label}",
                    key=f"unmark_{requirement_id}",
                ):
                    try:
                        repository.unmark_file_sent(requirement_id)
                    except APIError as exc:
                        st.error(exc.message)
                    else:
                        st.rerun()
                continue

            if st.button(
                f"Mark {label} as sent",
                key=f"mark_{requirement_id}",
                type="primary",
            ):
                try:
                    cleaned = (
                        _normalize_share_url(url_value)
                        if url_value.strip()
                        else ""
                    )
                    repository.mark_file_sent(
                        requirement_id,
                        share_url=cleaned or None,
                    )
                except (APIError, ValueError) as exc:
                    message = getattr(exc, "message", None) or str(exc)
                    st.error(message)
                else:
                    st.success(f"{label} marked as sent.")
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
        "corrections_sent",
    }:
        st.caption("Assign this case before reviewing files.")
        return

    requirements = _sorted_requirements(
        repository.list_requirements_for_case(case["id"])
    )
    for requirement in requirements:
        label = FILE_KIND_LABELS[requirement["kind"]]
        slot_state = file_slot_label(requirement["status"])
        url = requirement.get("external_url") or ""
        latest = requirement.get("latest_file")

        with st.container(border=True):
            st.markdown(f"**{label}** · {slot_state}")
            if requirement.get("replacement_reason"):
                st.caption(f"Last note: {requirement['replacement_reason']}")

            if url:
                st.link_button("Open OneDrive link", url)
            elif latest:
                try:
                    download_url = repository.create_signed_download_url(
                        latest["storage_path"]
                    )
                    st.link_button("Download (legacy upload)", download_url)
                except Exception as exc:
                    st.error(f"Download unavailable: {exc}")
            else:
                st.caption("Not sent yet.")
                continue

            if requirement["status"] == "accepted":
                st.success("Already accepted.")
                continue

            if requirement["status"] not in SENT_STATUSES | {"replacement_requested"}:
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
                    repository.review_file_requirement(
                        requirement_id=requirement["id"],
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
                    repository.review_file_requirement(
                        requirement_id=requirement["id"],
                        decision="rejected",
                        note=note,
                    )
                except APIError as exc:
                    st.error(exc.message)
                    continue
                st.warning(f"{label} marked for replacement.")
                st.rerun()
