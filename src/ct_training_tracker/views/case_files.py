"""Case file link submission and review widgets (OneDrive links)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import streamlit as st
from postgrest.exceptions import APIError

from ct_training_tracker.files import (
    FILE_KIND_LABELS,
    PACKAGE_EDITABLE_STATUSES,
    PACKAGE_WITH_TRAINER_STATUSES,
    READY_SLOT_STATUSES,
    can_submit_package,
    count_ready_slots,
)
from ct_training_tracker.metrics import file_slot_label
from ct_training_tracker.repository import TrainingRepository

KIND_ORDER = ("pdf_primary", "pdf_secondary", "ov")


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
    trainer_name: str | None = None,
) -> None:
    del user_id  # Auth comes from the session client / RPC.
    status = case["status"]
    if status not in PACKAGE_EDITABLE_STATUSES | PACKAGE_WITH_TRAINER_STATUSES:
        st.caption(
            "This case is not ready for file links yet "
            f"(status: {str(status).replace('_', ' ')})."
        )
        return

    requirements = _sorted_requirements(
        repository.list_requirements_for_case(case["id"])
    )
    ready = count_ready_slots(requirements)
    reviewer = (trainer_name or "").strip() or "Your trainer"

    if status in PACKAGE_WITH_TRAINER_STATUSES:
        st.success(
            "Submitted for review",
            icon=":material/hourglass_top:",
        )
        st.caption(f"{reviewer} is reviewing — please wait.")
        for requirement in requirements:
            label = FILE_KIND_LABELS[requirement["kind"]]
            current_url = requirement.get("external_url") or ""
            with st.container(border=True):
                left, right = st.columns([2, 1])
                left.markdown(f"**{label}**")
                right.badge("With trainer", color="blue")
                if current_url:
                    st.link_button("Open link", current_url)
                else:
                    st.caption("No link on file.")
        return

    st.caption(f"Package progress: {ready}/3 ready")

    for requirement in requirements:
        label = FILE_KIND_LABELS[requirement["kind"]]
        slot_state = file_slot_label(requirement["status"])
        requirement_id = requirement["id"]
        current_url = requirement.get("external_url") or ""

        with st.container(border=True):
            head = st.columns([2, 1])
            head[0].markdown(f"**{label}**")
            if requirement["status"] == "accepted":
                head[1].badge("Accepted", color="green")
            elif requirement["status"] in READY_SLOT_STATUSES:
                head[1].badge("Ready", color="blue")
            elif requirement["status"] == "replacement_requested":
                head[1].badge("Replace", color="orange")
            else:
                head[1].badge(slot_state, color="gray")

            if requirement.get("replacement_reason"):
                st.warning(requirement["replacement_reason"])

            if requirement["status"] == "accepted":
                if current_url:
                    st.link_button("Open link", current_url)
                st.caption("Nothing else to send for this slot.")
                continue

            url_value = st.text_input(
                f"{label} OneDrive link",
                value=current_url,
                key=f"link_{requirement_id}",
                placeholder="https://…onedrive…/…",
                label_visibility="collapsed",
            )
            st.caption("OneDrive share link")

            if requirement["status"] in READY_SLOT_STATUSES:
                actions = st.columns(2)
                if current_url:
                    actions[0].link_button("Open link", current_url)
                if actions[1].button(
                    "Undo",
                    key=f"unmark_{requirement_id}",
                    width="stretch",
                ):
                    try:
                        repository.unmark_file_sent(requirement_id)
                    except APIError as exc:
                        st.error(exc.message)
                    else:
                        st.rerun()
                continue

            if st.button(
                f"Mark {label} ready",
                key=f"mark_{requirement_id}",
                type="primary",
                width="stretch",
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
                    st.toast(f"{label} ready")
                    st.rerun()

    if can_submit_package(status, requirements):
        if st.button(
            "Notify trainer for review",
            key=f"submit_package_{case['id']}",
            type="primary",
            width="stretch",
            icon=":material/send:",
        ):
            try:
                repository.submit_case_for_review(case["id"])
            except APIError as exc:
                st.error(exc.message)
            else:
                st.toast("Submitted for review")
                st.rerun()
    elif status in PACKAGE_EDITABLE_STATUSES:
        st.caption("Mark all three slots ready before notifying the trainer.")


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

    if case["status"] in PACKAGE_WITH_TRAINER_STATUSES:
        st.caption(
            "Open links, then review in the Review tab. "
            "Send back only if a file is wrong."
        )
    elif case["status"] == "awaiting_resubmission":
        st.caption("Waiting for the trainee to fix and resubmit.")
    else:
        st.caption("Trainee is still preparing the package.")

    requirements = _sorted_requirements(
        repository.list_requirements_for_case(case["id"])
    )
    for requirement in requirements:
        label = FILE_KIND_LABELS[requirement["kind"]]
        slot_state = file_slot_label(requirement["status"])
        url = requirement.get("external_url") or ""
        latest = requirement.get("latest_file")

        with st.container(border=True):
            head = st.columns([2, 1])
            head[0].markdown(f"**{label}**")
            if requirement["status"] == "accepted":
                head[1].badge("Accepted", color="green")
            elif requirement["status"] in READY_SLOT_STATUSES:
                head[1].badge(slot_state, color="blue")
            elif requirement["status"] == "replacement_requested":
                head[1].badge("Replace", color="orange")
            else:
                head[1].badge(slot_state, color="gray")

            if requirement.get("replacement_reason"):
                st.caption(requirement["replacement_reason"])

            if url:
                st.link_button("Open link", url)
            elif latest:
                try:
                    download_url = repository.create_signed_download_url(
                        latest["storage_path"]
                    )
                    st.link_button("Download (legacy)", download_url)
                except Exception as exc:
                    st.error(f"Download unavailable: {exc}")
            else:
                st.caption("Not sent yet.")
                continue

            if requirement["status"] == "accepted":
                continue

            if requirement["status"] not in READY_SLOT_STATUSES | {
                "replacement_requested"
            }:
                continue

            if case["status"] not in PACKAGE_WITH_TRAINER_STATUSES | {
                "awaiting_resubmission"
            }:
                continue

            note = st.text_input(
                "Replacement note",
                key=f"review_note_{requirement['id']}",
                placeholder="Why this slot needs to be resent",
                label_visibility="collapsed",
            )
            st.caption("Optional note if requesting replacement")
            if st.button(
                f"Request replacement · {label}",
                key=f"reject_{requirement['id']}",
                width="stretch",
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
                st.toast(f"{label} sent back")
                st.rerun()
