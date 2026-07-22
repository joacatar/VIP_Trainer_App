"""Revision and correction UI for trainer and trainee portals."""

from __future__ import annotations

from typing import Any

import streamlit as st
from postgrest.exceptions import APIError

from ct_training_tracker.components.paste_image import (
    PastedImage,
    clear_comment_draft,
    comment_box,
)
from ct_training_tracker.repository import TrainingRepository
from ct_training_tracker.revisions import (
    can_start_revision,
    checklist_for_section,
    count_open_corrections_in_tree,
    feedback_bodies,
    partition_sections_by_feedback,
    section_label,
)


def _upload_images(
    repository: TrainingRepository,
    *,
    user_id: str,
    case_id: str,
    correction_id: str,
    images: list[PastedImage],
) -> None:
    for image in images:
        repository.upload_correction_screenshot(
            user_id=user_id,
            case_id=case_id,
            correction_id=correction_id,
            filename=image.filename,
            content=image.content,
            mime_type=image.mime_type,
        )


def _render_optional_upload(*, upload_key: str) -> list[PastedImage]:
    images: list[PastedImage] = []
    with st.expander("Upload from disk", icon=":material/upload_file:"):
        uploaded = st.file_uploader(
            "Screenshot files",
            type=["png", "jpg", "jpeg", "webp", "gif"],
            accept_multiple_files=True,
            key=upload_key,
            label_visibility="collapsed",
        )
        if uploaded:
            for file in uploaded:
                images.append(
                    PastedImage(
                        filename=file.name,
                        mime_type=file.type or "application/octet-stream",
                        content=file.getvalue(),
                    )
                )
    return images


def _render_screenshots(
    repository: TrainingRepository,
    screenshots: list[dict[str, Any]],
    *,
    key_prefix: str,
) -> None:
    if not screenshots:
        return

    loaded: list[tuple[dict[str, Any], bytes | None, str | None]] = []
    for shot in screenshots:
        try:
            data = repository.download_storage_bytes(shot["storage_path"])
            loaded.append((shot, data, None))
        except Exception as exc:
            loaded.append((shot, None, str(exc)))

    visible = [(shot, data) for shot, data, error in loaded if data is not None]
    if visible:
        st.caption(f"{len(visible)} screenshot(s)")
        thumb_cols = st.columns(min(4, len(visible)))
        for col, (_shot, data) in zip(thumb_cols, visible, strict=False):
            with col:
                st.image(data, use_container_width=True)

    for index, (shot, data, error) in enumerate(loaded):
        label = shot.get("original_filename") or f"Screenshot {index + 1}"
        with st.expander(
            f"Expand · {label}",
            expanded=len(loaded) == 1,
            icon=":material/zoom_in:",
        ):
            if data is None:
                st.error(f"Could not load screenshot: {error}")
                continue
            st.image(data, use_container_width=True)
            try:
                url = repository.create_signed_download_url(shot["storage_path"])
                st.link_button(
                    "Open full size",
                    url,
                    width="stretch",
                    key=f"{key_prefix}_open_{shot.get('id', index)}",
                )
            except Exception as exc:
                st.caption(f"Open link unavailable: {exc}")


def _render_protocol_chips(revision: dict[str, Any]) -> None:
    needs, ok = partition_sections_by_feedback(revision)
    need_labels = [
        (
            f"{section_label(section['section_key'])} "
            f"({len(section.get('corrections') or [])})"
        )
        for section in needs
    ]
    ok_labels = [section_label(section["section_key"]) for section in ok]

    top = st.columns([1.2, 1])
    with top[0]:
        st.markdown("**Needs work**")
        if need_labels:
            st.markdown(
                " ".join(f":orange-badge[{label}]" for label in need_labels)
            )
        else:
            st.caption("Nothing flagged yet.")
    with top[1]:
        st.markdown("**Looks good**")
        if ok_labels:
            st.markdown(" ".join(f":green-badge[{label}]" for label in ok_labels))
        else:
            st.caption("Every section has corrections.")


def _correction_badge(status: str) -> None:
    if status == "resolved":
        st.badge("Resolved", icon=":material/check_circle:", color="green")
    else:
        st.badge("Open", icon=":material/pending:", color="orange")


def _render_correction_card(
    repository: TrainingRepository,
    *,
    user_id: str,
    case_id: str,
    correction: dict[str, Any],
    is_draft: bool,
) -> None:
    status = str(correction.get("status") or "open")
    with st.container(border=True):
        head = st.columns([1.4, 1])
        with head[0]:
            _correction_badge(status)
        with head[1]:
            if is_draft:
                if status == "open":
                    if st.button(
                        "Resolve",
                        key=f"resolve_{correction['id']}",
                        width="stretch",
                    ):
                        try:
                            repository.set_correction_status(
                                correction["id"],
                                "resolved",
                            )
                        except APIError as exc:
                            st.error(exc.message)
                        else:
                            st.toast("Marked resolved")
                            st.rerun()
                else:
                    if st.button(
                        "Reopen",
                        key=f"reopen_{correction['id']}",
                        width="stretch",
                    ):
                        try:
                            repository.set_correction_status(
                                correction["id"],
                                "open",
                            )
                        except APIError as exc:
                            st.error(exc.message)
                        else:
                            st.toast("Reopened")
                            st.rerun()

        st.write(correction.get("body") or "")
        if correction.get("rolled_from_correction_id"):
            st.caption("Carried forward from a previous revision.")
        _render_screenshots(
            repository,
            correction.get("correction_screenshots") or [],
            key_prefix=f"corr_{correction['id']}",
        )

        if not is_draft:
            return

        with st.expander(
            "Add screenshots",
            icon=":material/image:",
        ):
            draft_key = f"comment_attach_{correction['id']}"
            draft = comment_box(
                key=draft_key,
                placeholder="Paste screenshots here (Ctrl+V / Cmd+V)",
            )
            disk_images = _render_optional_upload(
                upload_key=f"shot_{correction['id']}",
            )
            if st.button(
                "Save screenshots",
                key=f"attach_shot_{correction['id']}",
                type="primary",
            ):
                images = list(draft.images) + list(disk_images)
                if not images:
                    st.warning("Paste or upload a screenshot first.")
                else:
                    try:
                        _upload_images(
                            repository,
                            user_id=user_id,
                            case_id=case_id,
                            correction_id=correction["id"],
                            images=images,
                        )
                    except (APIError, ValueError, Exception) as exc:
                        message = getattr(exc, "message", None) or str(exc)
                        st.error(message)
                    else:
                        clear_comment_draft(draft_key)
                        st.toast(f"Attached {len(images)} screenshot(s)")
                        st.rerun()


def _render_visible_checklist(
    *,
    section_id: str,
    options: list[str],
) -> list[str]:
    selected: list[str] = []
    if not options:
        return selected
    st.caption("Check only what needs fixing. Leave blank if this section is OK.")
    for index, item in enumerate(options):
        if st.checkbox(item, key=f"check_{section_id}_{index}"):
            selected.append(item)
    return selected


def _render_section_feedback_composer(
    repository: TrainingRepository,
    *,
    user_id: str,
    case_id: str,
    section: dict[str, Any],
) -> None:
    section_id = section["id"]
    section_key = section["section_key"]
    options = list(checklist_for_section(section_key))

    with st.container(border=True):
        st.markdown("**Add feedback**")
        selected = _render_visible_checklist(
            section_id=section_id,
            options=options,
        )
        st.markdown("**Comment + screenshots**")
        draft_key = f"section_comment_{section_id}"
        draft = comment_box(
            key=draft_key,
            placeholder="Notes… paste screenshots with Ctrl+V / Cmd+V",
        )
        disk_images = _render_optional_upload(
            upload_key=f"pending_shots_{section_id}",
        )

        save = st.button(
            "Save feedback",
            key=f"add_feedback_{section_id}",
            type="primary",
            width="stretch",
        )
        if not save:
            return

        bodies = feedback_bodies(selected, draft.text)
        shots = list(draft.images) + list(disk_images)
        if not bodies and not shots:
            st.toast("Section left as OK — no corrections saved")
            return
        if not bodies and shots:
            bodies = ["See attached screenshot(s)."]

        created_ids: list[str] = []
        try:
            for body in bodies:
                correction_id = repository.add_correction(
                    section_id=section_id,
                    body=body,
                    severity="minor",
                )
                created_ids.append(correction_id)
            if shots and created_ids:
                target_id = (
                    created_ids[-1]
                    if draft.text.strip() or len(bodies) == 1
                    else created_ids[0]
                )
                _upload_images(
                    repository,
                    user_id=user_id,
                    case_id=case_id,
                    correction_id=target_id,
                    images=shots,
                )
        except (APIError, ValueError, Exception) as exc:
            message = getattr(exc, "message", None) or str(exc)
            st.error(message)
            return

        clear_comment_draft(draft_key)
        st.toast(f"Saved {len(created_ids)} correction(s)")
        st.rerun()


def _pick_section(
    sections: list[dict[str, Any]],
    *,
    key: str,
) -> dict[str, Any]:
    options = [section["section_key"] for section in sections]

    def _label(section_key: str) -> str:
        section = next(row for row in sections if row["section_key"] == section_key)
        count = len(section.get("corrections") or [])
        name = section_label(section_key)
        return f"{name} · {count}" if count else f"{name} · OK"

    selected_key = st.pills(
        "Section",
        options=options,
        format_func=_label,
        key=key,
        selection_mode="single",
        default=options[0],
        required=True,
    )
    return next(row for row in sections if row["section_key"] == selected_key)


def render_trainee_revisions(
    repository: TrainingRepository,
    *,
    case: dict[str, Any],
) -> None:
    st.subheader("Review feedback")
    revisions = repository.list_revisions_for_case(
        case["id"],
        published_only=True,
    )
    if not revisions:
        st.caption("No published review yet.")
        return

    labels = {
        row["id"]: f"Revision {row['revision_no']}"
        for row in revisions
    }
    revision_id = st.selectbox(
        "Revision",
        options=list(labels),
        format_func=lambda value: labels[value],
        key=f"trainee_revision_{case['id']}",
        label_visibility="collapsed",
    )
    revision = next(row for row in revisions if row["id"] == revision_id)
    open_count = count_open_corrections_in_tree(revision)

    meta = st.columns([1, 1, 1])
    meta[0].metric("Open items", open_count)
    needs, ok = partition_sections_by_feedback(revision)
    meta[1].metric("Sections to fix", len(needs))
    meta[2].metric("Sections OK", len(ok))

    _render_protocol_chips(revision)

    st.markdown("#### What to fix")
    if not needs:
        st.success(
            "No corrections — this package looks good.",
            icon=":material/check_circle:",
        )
    else:
        for section in needs:
            corrections = section.get("corrections") or []
            title = section_label(section["section_key"])
            with st.expander(
                f"{title} · {len(corrections)} item(s)",
                expanded=True,
                icon=":material/build:",
            ):
                for correction in corrections:
                    with st.container(border=True):
                        _correction_badge(str(correction.get("status") or "open"))
                        st.write(correction.get("body") or "")
                        _render_screenshots(
                            repository,
                            correction.get("correction_screenshots") or [],
                            key_prefix=f"trainee_corr_{correction['id']}",
                        )

    if ok:
        st.markdown("#### Already good")
        st.markdown(
            " ".join(
                f":green-badge[{section_label(section['section_key'])}]"
                for section in ok
            )
        )


def render_trainer_revisions(
    repository: TrainingRepository,
    *,
    user_id: str,
    case: dict[str, Any],
) -> None:
    st.subheader("Review")
    status = case["status"]
    revisions = repository.list_revisions_for_case(case["id"])
    draft = next((row for row in revisions if row["status"] == "draft"), None)

    if can_start_revision(status) and draft is None:
        st.caption("Open a draft to leave section feedback for this package.")
        if st.button(
            "Start review",
            key=f"start_revision_{case['id']}",
            type="primary",
            icon=":material/rate_review:",
        ):
            try:
                repository.create_revision(case["id"])
            except APIError as exc:
                st.error(exc.message)
            else:
                st.toast("Draft review started")
                st.rerun()
        if not revisions:
            return
    elif not can_start_revision(status) and draft is None and not revisions:
        st.caption(
            "Review unlocks after the trainee submits the package."
        )
        return

    if not revisions:
        return

    labels = {
        row["id"]: (
            f"Revision {row['revision_no']} · {row['status']}"
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

    toolbar = st.columns([2.2, 1])
    with toolbar[0]:
        revision_id = st.selectbox(
            "Revision",
            options=options,
            index=index,
            format_func=lambda value: labels[value],
            key=f"trainer_revision_{case['id']}",
            label_visibility="collapsed",
        )
    revision = next(row for row in revisions if row["id"] == revision_id)
    is_draft = revision["status"] == "draft"

    with toolbar[1]:
        if is_draft:
            if st.button(
                "Publish",
                key=f"publish_revision_{revision_id}",
                type="primary",
                width="stretch",
                icon=":material/send:",
            ):
                try:
                    repository.publish_revision(revision_id)
                except APIError as exc:
                    st.error(exc.message)
                else:
                    st.toast("Published to trainee")
                    st.rerun()
        else:
            st.badge("Published", icon=":material/lock:", color="blue")

    if is_draft:
        st.caption(
            "Empty sections stay OK. Only save feedback where something is wrong."
        )
    _render_protocol_chips(revision)

    sections = revision["revision_sections"]
    section = _pick_section(
        sections,
        key=f"trainer_section_{revision_id}",
    )
    corrections = section.get("corrections") or []
    title = section_label(section["section_key"])

    if corrections:
        st.markdown(f"**{title}** · {len(corrections)} saved")
        for correction in corrections:
            _render_correction_card(
                repository,
                user_id=user_id,
                case_id=case["id"],
                correction=correction,
                is_draft=is_draft,
            )
    else:
        st.success(
            f"{title} is OK — no corrections saved yet.",
            icon=":material/check_circle:",
        )

    if is_draft:
        _render_section_feedback_composer(
            repository,
            user_id=user_id,
            case_id=case["id"],
            section=section,
        )
