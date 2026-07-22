"""Revision and correction UI for trainer and trainee portals."""

from __future__ import annotations

from typing import Any

import streamlit as st
from postgrest.exceptions import APIError

from ct_training_tracker.repository import TrainingRepository
from ct_training_tracker.revisions import (
    can_start_revision,
    count_open_corrections_in_tree,
    section_label,
)


def _render_screenshots(
    repository: TrainingRepository,
    screenshots: list[dict[str, Any]],
) -> None:
    if not screenshots:
        return
    for shot in screenshots:
        cols = st.columns([3, 1])
        cols[0].caption(shot.get("original_filename") or "screenshot")
        try:
            url = repository.create_signed_download_url(shot["storage_path"])
            cols[1].link_button("Open", url)
        except Exception as exc:
            cols[1].caption(f"Unavailable: {exc}")


def _render_correction_readonly(
    repository: TrainingRepository,
    correction: dict[str, Any],
) -> None:
    severity = str(correction.get("severity", "minor")).title()
    status = str(correction.get("status", "open")).title()
    with st.container(border=True):
        st.markdown(f"**{severity}** · {status}")
        st.write(correction.get("body") or "")
        if correction.get("rolled_from_correction_id"):
            st.caption("Carried forward from a previous revision.")
        _render_screenshots(
            repository,
            correction.get("correction_screenshots") or [],
        )


def render_trainee_revisions(
    repository: TrainingRepository,
    *,
    case: dict[str, Any],
) -> None:
    st.markdown("##### Revisions")
    revisions = repository.list_revisions_for_case(
        case["id"],
        published_only=True,
    )
    if not revisions:
        st.caption("No published revisions yet.")
        return

    labels = {
        row["id"]: (
            f"Revision {row['revision_no']} · "
            f"{row.get('published_at') or row.get('created_at') or ''}"
        )
        for row in revisions
    }
    revision_id = st.selectbox(
        "Published revision",
        options=list(labels),
        format_func=lambda value: labels[value],
        key=f"trainee_revision_{case['id']}",
    )
    revision = next(row for row in revisions if row["id"] == revision_id)
    open_count = count_open_corrections_in_tree(revision)
    st.caption(f"{open_count} open correction(s) in this revision.")

    for section in revision.get("revision_sections") or []:
        corrections = section.get("corrections") or []
        title = section_label(section["section_key"])
        with st.expander(
            f"{title} · {len(corrections)} correction(s)",
            expanded=bool(corrections),
        ):
            if not corrections:
                st.caption("No corrections in this section.")
                continue
            for correction in corrections:
                _render_correction_readonly(repository, correction)


def render_trainer_revisions(
    repository: TrainingRepository,
    *,
    user_id: str,
    case: dict[str, Any],
) -> None:
    st.markdown("##### Revisions")
    status = case["status"]
    revisions = repository.list_revisions_for_case(case["id"])
    draft = next((row for row in revisions if row["status"] == "draft"), None)

    if can_start_revision(status) and draft is None:
        if st.button(
            "Start revision",
            key=f"start_revision_{case['id']}",
            type="primary",
        ):
            try:
                repository.create_revision(case["id"])
            except APIError as exc:
                st.error(exc.message)
            else:
                st.success("Draft revision created.")
                st.rerun()
    elif not can_start_revision(status) and draft is None and not revisions:
        st.caption(
            "Revisions unlock when all three files are accepted "
            "(case status: in review)."
        )

    if not revisions:
        return

    labels = {
        row["id"]: (
            f"Revision {row['revision_no']} · {row['status'].title()}"
            + (
                f" · {count_open_corrections_in_tree(row)} open"
                if row["status"] == "draft"
                else ""
            )
        )
        for row in revisions
    }
    default_id = draft["id"] if draft else revisions[0]["id"]
    options = list(labels)
    index = options.index(default_id) if default_id in labels else 0
    revision_id = st.selectbox(
        "Revision",
        options=options,
        index=index,
        format_func=lambda value: labels[value],
        key=f"trainer_revision_{case['id']}",
    )
    revision = next(row for row in revisions if row["id"] == revision_id)
    is_draft = revision["status"] == "draft"

    if is_draft:
        publish_col, _ = st.columns([1, 2])
        if publish_col.button(
            "Publish to trainee",
            key=f"publish_revision_{revision_id}",
            type="primary",
        ):
            try:
                repository.publish_revision(revision_id)
            except APIError as exc:
                st.error(exc.message)
            else:
                st.success("Revision published.")
                st.rerun()
    else:
        st.caption("Published revisions are read-only.")

    sections = revision["revision_sections"]
    section_tabs = st.tabs(
        [section_label(section["section_key"]) for section in sections]
    )
    for tab, section in zip(section_tabs, sections, strict=True):
        with tab:
            corrections = section.get("corrections") or []
            if not corrections:
                st.caption("No corrections yet.")
            for correction in corrections:
                with st.container(border=True):
                    severity = str(correction.get("severity", "minor")).title()
                    status_label = str(correction.get("status", "open")).title()
                    st.markdown(f"**{severity}** · {status_label}")
                    st.write(correction.get("body") or "")
                    if correction.get("rolled_from_correction_id"):
                        st.caption("Carried forward from a previous revision.")
                    _render_screenshots(
                        repository,
                        correction.get("correction_screenshots") or [],
                    )
                    if is_draft:
                        action_cols = st.columns(2)
                        if correction["status"] == "open":
                            if action_cols[0].button(
                                "Mark resolved",
                                key=f"resolve_{correction['id']}",
                            ):
                                try:
                                    repository.set_correction_status(
                                        correction["id"],
                                        "resolved",
                                    )
                                except APIError as exc:
                                    st.error(exc.message)
                                else:
                                    st.rerun()
                        else:
                            if action_cols[0].button(
                                "Reopen",
                                key=f"reopen_{correction['id']}",
                            ):
                                try:
                                    repository.set_correction_status(
                                        correction["id"],
                                        "open",
                                    )
                                except APIError as exc:
                                    st.error(exc.message)
                                else:
                                    st.rerun()

                        uploaded = st.file_uploader(
                            "Attach screenshot (png/jpg)",
                            type=["png", "jpg", "jpeg", "webp", "gif"],
                            key=f"shot_{correction['id']}",
                            help="Upload a screenshot for this correction.",
                        )
                        if uploaded is not None and st.button(
                            "Upload screenshot",
                            key=f"upload_shot_{correction['id']}",
                        ):
                            try:
                                repository.upload_correction_screenshot(
                                    user_id=user_id,
                                    case_id=case["id"],
                                    correction_id=correction["id"],
                                    filename=uploaded.name,
                                    content=uploaded.getvalue(),
                                    mime_type=uploaded.type,
                                )
                            except (APIError, ValueError, Exception) as exc:
                                message = getattr(exc, "message", None) or str(exc)
                                st.error(message)
                            else:
                                st.success("Screenshot attached.")
                                st.rerun()

            if is_draft:
                with st.form(f"add_correction_{section['id']}"):
                    body = st.text_area(
                        "New correction",
                        placeholder="What should the trainee fix?",
                    )
                    severity = st.selectbox(
                        "Severity",
                        options=["minor", "major"],
                        format_func=str.title,
                    )
                    submitted = st.form_submit_button("Add correction", type="primary")
                if submitted:
                    try:
                        repository.add_correction(
                            section_id=section["id"],
                            body=body,
                            severity=severity,
                        )
                    except APIError as exc:
                        st.error(exc.message)
                    else:
                        st.success("Correction added.")
                        st.rerun()
