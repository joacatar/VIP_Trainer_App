"""Revision and correction UI for trainer and trainee portals."""

from __future__ import annotations

from typing import Any

import streamlit as st
from postgrest.exceptions import APIError

from ct_training_tracker.case_labels import case_title
from ct_training_tracker.components.paste_image import (
    PastedImage,
    clear_comment_draft,
    comment_box,
)
from ct_training_tracker.files import FILE_KIND_LABELS, READY_SLOT_STATUSES
from ct_training_tracker.repository import TrainingRepository
from ct_training_tracker.revisions import (
    can_start_revision,
    checklist_for_section,
    count_open_corrections_in_tree,
    feedback_bodies,
    partition_sections_by_feedback,
    section_label,
    section_open_correction_count,
)
from ct_training_tracker.storage_cache import cached_storage_bytes

KIND_ORDER = ("pdf_primary", "pdf_secondary", "ov")


def _render_feedback_context(
    case: dict[str, Any],
    *,
    revision: dict[str, Any] | None = None,
) -> None:
    """Repeat critical case identity inside Feedback to prevent mix-ups."""
    with st.container(border=True, horizontal=True, vertical_alignment="center"):
        with st.container():
            st.caption("Currently reviewing")
            st.markdown(f"**{case.get('trainee_name') or 'Trainee'}**")
        with st.container():
            st.caption("Case")
            st.markdown(f"**{case_title(case)}**")
        with st.container():
            st.caption("Feedback status")
            if revision is None:
                st.markdown("_No feedback started yet_")
            else:
                needs, ok = partition_sections_by_feedback(revision)
                open_count = count_open_corrections_in_tree(revision)
                if not needs:
                    st.markdown(":green[All sections OK]")
                else:
                    st.markdown(
                        f":orange[{len(needs)} section(s) need fixes] "
                        f"({open_count} open) · :green[{len(ok)} OK]"
                    )


def _sorted_requirements(requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order = {kind: index for index, kind in enumerate(KIND_ORDER)}
    return sorted(requirements, key=lambda row: order.get(row["kind"], 99))


def _collect_file_draft_decisions(
    requirements: list[dict[str, Any]],
    *,
    case_id: str,
) -> list[dict[str, str]]:
    """Read draft replacement toggles from session widgets."""
    decisions: list[dict[str, str]] = []
    for requirement in requirements:
        if requirement["status"] not in READY_SLOT_STATUSES | {
            "replacement_requested"
        }:
            continue
        if requirement["status"] == "accepted":
            continue
        req_id = str(requirement["id"])
        needs = bool(
            st.session_state.get(f"draft_replace_{case_id}_{req_id}", False)
        )
        note = str(
            st.session_state.get(f"draft_replace_note_{case_id}_{req_id}", "")
            or ""
        ).strip()
        if needs:
            decisions.append(
                {
                    "requirement_id": req_id,
                    "decision": "rejected",
                    "note": note,
                }
            )
    return decisions


def _render_file_draft_panel(
    requirements: list[dict[str, Any]],
    *,
    case_id: str,
    editable: bool,
) -> None:
    """Silent draft flags for files — applied only on publish."""
    reviewable = [
        row
        for row in requirements
        if row["status"] in READY_SLOT_STATUSES | {"replacement_requested"}
        or row["status"] == "accepted"
    ]
    if not reviewable:
        return

    st.markdown("#### 1. Package files")
    st.caption(
        "Mark files that need replacement. Nothing is sent until you publish."
    )
    for requirement in reviewable:
        label = FILE_KIND_LABELS[requirement["kind"]]
        req_id = str(requirement["id"])
        url = requirement.get("external_url") or ""
        with st.container(border=True):
            head = st.columns([2, 1], vertical_alignment="center")
            head[0].markdown(f"**{label}**")
            if requirement["status"] == "accepted":
                head[1].badge("Accepted", color="green")
            elif requirement["status"] == "replacement_requested":
                head[1].badge("Replace pending", color="orange")
            else:
                head[1].badge("In review", color="blue")
            if url:
                st.link_button("Open link", url, width="content")
            if not editable or requirement["status"] == "accepted":
                continue
            needs = st.checkbox(
                "Needs replacement",
                key=f"draft_replace_{case_id}_{req_id}",
            )
            if needs:
                st.text_input(
                    "Why this file needs to be resent",
                    key=f"draft_replace_note_{case_id}_{req_id}",
                    placeholder="Optional note for the trainee",
                )


def _render_publish_action_bar(
    repository: TrainingRepository,
    *,
    case: dict[str, Any],
    revision_id: str | None,
    requirements: list[dict[str, Any]],
    is_draft: bool,
    open_feedback: int = 0,
) -> None:
    """Single consolidation point: return package or approve."""
    if case["status"] not in {"in_review", "corrections_sent"}:
        return

    decisions = _collect_file_draft_decisions(
        requirements,
        case_id=case["id"],
    )

    with st.container(border=True):
        st.markdown("**3. Finish**")
        parts: list[str] = []
        if decisions:
            parts.append(f"{len(decisions)} file(s) marked for replacement")
        if open_feedback:
            parts.append(f"{open_feedback} correction(s) ready to publish")
        if not parts:
            parts.append(
                "No replacements marked. Publish feedback only, or approve the package."
            )
        st.caption(" · ".join(parts))

        publish_col, approve_col = st.columns(2)
        with publish_col:
            can_publish = bool(decisions) or (is_draft and revision_id is not None)
            if st.button(
                "Publish review & notify trainee",
                key=f"publish_case_review_{case['id']}",
                type="primary",
                width="stretch",
                icon=":material/send:",
                disabled=not can_publish,
            ):
                try:
                    repository.publish_case_review(
                        case_id=case["id"],
                        revision_id=revision_id if is_draft else None,
                        file_decisions=decisions,
                        approve_package=False,
                    )
                except APIError as exc:
                    st.error(exc.message)
                else:
                    st.toast("Review published")
                    st.rerun()
        with approve_col:
            if st.button(
                "Approve case",
                key=f"approve_case_{case['id']}",
                width="stretch",
                icon=":material/check_circle:",
                disabled=bool(decisions),
                help=(
                    "Accepts all files and closes the case. "
                    "Clear replacement marks first."
                ),
            ):
                try:
                    accept_all = [
                        {
                            "requirement_id": str(row["id"]),
                            "decision": "accepted",
                            "note": "",
                        }
                        for row in requirements
                        if row["status"] in READY_SLOT_STATUSES
                    ]
                    repository.publish_case_review(
                        case_id=case["id"],
                        revision_id=revision_id if is_draft else None,
                        file_decisions=accept_all,
                        approve_package=True,
                    )
                except APIError as exc:
                    st.error(exc.message)
                else:
                    st.toast("Case approved")
                    st.rerun()


def render_trainer_revisions(
    repository: TrainingRepository,
    *,
    user_id: str,
    case: dict[str, Any],
) -> None:
    st.subheader("Feedback")
    _clear_section_overrides()
    status = case["status"]
    requirements = _sorted_requirements(
        repository.list_requirements_for_case(case["id"])
    )
    revisions = repository.list_revisions_for_case(case["id"])
    draft = next((row for row in revisions if row["status"] == "draft"), None)
    can_edit_files = status in {"in_review", "corrections_sent"}
    _render_feedback_context(
        case,
        revision=draft or (revisions[0] if revisions else None),
    )

    if can_start_revision(status) and draft is None:
        st.caption("Start a feedback draft for anatomy sections, then publish once.")
        if st.button(
            "Start feedback draft",
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
            _render_file_draft_panel(
                requirements,
                case_id=case["id"],
                editable=can_edit_files,
            )
            _render_publish_action_bar(
                repository,
                case=case,
                revision_id=None,
                requirements=requirements,
                is_draft=False,
                open_feedback=0,
            )
            return
    elif not can_start_revision(status) and draft is None and not revisions:
        st.caption("Review unlocks after the trainee submits the package.")
        return

    if not revisions:
        _render_file_draft_panel(
            requirements,
            case_id=case["id"],
            editable=can_edit_files,
        )
        _render_publish_action_bar(
            repository,
            case=case,
            revision_id=None,
            requirements=requirements,
            is_draft=False,
            open_feedback=0,
        )
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
    if not is_draft:
        st.badge("Published", icon=":material/lock:", color="blue")

    _render_file_draft_panel(
        requirements,
        case_id=case["id"],
        editable=is_draft or can_edit_files,
    )

    st.markdown("#### 2. Section feedback")
    st.caption(
        "Open a section to see every saved correction and add another entry."
    )
    _render_protocol_chips(revision)

    sections = revision["revision_sections"]
    any_open = count_open_corrections_in_tree(revision) > 0
    for index, section in enumerate(sections):
        default_expanded = (
            section_open_correction_count(section) > 0 if any_open else index == 0
        )
        _render_section_panel(
            repository,
            user_id=user_id,
            case_id=case["id"],
            section=section,
            is_draft=is_draft,
            default_expanded=default_expanded,
        )

    _render_publish_action_bar(
        repository,
        case=case,
        revision_id=revision_id,
        requirements=requirements,
        is_draft=is_draft,
        open_feedback=count_open_corrections_in_tree(revision) if is_draft else 0,
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
            data = cached_storage_bytes(repository, shot["storage_path"])
            loaded.append((shot, data, None))
        except Exception as exc:
            loaded.append((shot, None, str(exc)))

    visible = [(shot, data) for shot, data, error in loaded if data is not None]
    if visible:
        st.caption(f"{len(visible)} screenshot(s)")
        thumb_cols = st.columns(min(4, len(visible)))
        for index, (col, (shot, data)) in enumerate(
            zip(thumb_cols, visible, strict=False)
        ):
            with col:
                st.image(data, width=220)
                try:
                    url = repository.create_signed_download_url(shot["storage_path"])
                    st.link_button(
                        "Zoom",
                        url,
                        width="content",
                        key=f"{key_prefix}_open_{shot.get('id', index)}",
                        icon=":material/zoom_in:",
                    )
                except Exception:
                    pass

    for index, (shot, _data, error) in enumerate(loaded):
        if error is None:
            continue
        label = shot.get("original_filename") or f"Screenshot {index + 1}"
        st.error(f"{label}: could not load — {error}")


def _render_protocol_chips(revision: dict[str, Any]) -> None:
    needs, ok = partition_sections_by_feedback(revision)
    need_labels = [
        (
            f"{section_label(section['section_key'])} "
            f"({section_open_correction_count(section)})"
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


def _section_override_key(section_id: str) -> str:
    return f"_section_override_{section_id}"


def _refresh_section_override(repository: TrainingRepository, section_id: str) -> None:
    """Patch just this section's data locally so a fragment-scoped rerun
    shows the change instantly without reloading the rest of the page."""
    fresh = repository.get_revision_section(section_id)
    if fresh is not None:
        st.session_state[_section_override_key(section_id)] = fresh


def _clear_section_overrides() -> None:
    """Drop stale in-fragment patches on every real full-page load, since
    the freshly fetched revision data becomes authoritative again."""
    prefix = "_section_override_"
    for key in [k for k in st.session_state if k.startswith(prefix)]:
        del st.session_state[key]


def _render_correction_card(
    repository: TrainingRepository,
    *,
    user_id: str,
    case_id: str,
    section_id: str,
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
                            _refresh_section_override(repository, section_id)
                            st.toast("Marked resolved")
                            st.rerun(scope="fragment")
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
                            _refresh_section_override(repository, section_id)
                            st.toast("Reopened")
                            st.rerun(scope="fragment")

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
                submit_label="Save screenshots",
            )
            disk_images = _render_optional_upload(
                upload_key=f"shot_{correction['id']}",
            )
            if draft.submitted:
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
                        _refresh_section_override(repository, section_id)
                        st.toast(f"Attached {len(images)} screenshot(s)")
                        st.rerun(scope="fragment")


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
        st.caption(
            "Checklist clicks stay in this box — the rest of the page will not jump."
        )
        selected = _render_visible_checklist(
            section_id=section_id,
            options=options,
        )
        st.markdown("**Comment + screenshots**")
        draft_key = f"section_comment_{section_id}"
        draft = comment_box(
            key=draft_key,
            placeholder="Notes… paste screenshots with Ctrl+V / Cmd+V",
            submit_label="Save feedback",
        )
        disk_images = _render_optional_upload(
            upload_key=f"pending_shots_{section_id}",
        )

        if not draft.submitted:
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
        _refresh_section_override(repository, section_id)
        st.toast(f"Saved {len(created_ids)} correction(s)")
        st.rerun(scope="fragment")


@st.fragment
def _render_section_panel(
    repository: TrainingRepository,
    *,
    user_id: str,
    case_id: str,
    section: dict[str, Any],
    is_draft: bool,
    default_expanded: bool,
) -> None:
    """One section's expander, corrections, and composer as a self-contained
    unit. Saving/resolving here reruns only this fragment (scope='fragment'),
    so the rest of the Feedback tab — and the user's scroll position — never
    jumps back to the top of the page."""
    section_id = section["id"]
    section_key = section["section_key"]
    live_section = st.session_state.get(_section_override_key(section_id), section)
    corrections = live_section.get("corrections") or []
    title = section_label(section_key)
    open_count = section_open_correction_count(live_section)
    if open_count:
        state = f"{open_count} open"
    elif corrections:
        state = "Resolved"
    else:
        state = "No corrections"

    panel = st.expander(
        f"{title} · {state}",
        expanded=default_expanded,
        key=f"section_panel_{case_id}_{section_key}",
        on_change="rerun",
        icon=":material/format_list_bulleted:",
    )
    if not panel.open:
        return
    with panel:
        if corrections:
            for correction_index, correction in enumerate(corrections, start=1):
                st.caption(f"Correction {correction_index}")
                _render_correction_card(
                    repository,
                    user_id=user_id,
                    case_id=case_id,
                    section_id=section_id,
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
                case_id=case_id,
                section=live_section,
            )


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

    st.markdown("#### Feedback by section")
    if not needs:
        st.success(
            "No corrections — this package looks good.",
            icon=":material/check_circle:",
        )

    for section in revision.get("revision_sections") or []:
        corrections = section.get("corrections") or []
        open_items = [
            correction
            for correction in corrections
            if correction.get("status") == "open"
        ]
        title = section_label(section["section_key"])
        if open_items:
            state = f"{len(open_items)} to fix"
            icon = ":material/build:"
        elif corrections:
            state = "Resolved"
            icon = ":material/check_circle:"
        else:
            state = "OK"
            icon = ":material/check_circle:"

        panel = st.expander(
            f"{title} · {state}",
            expanded=bool(open_items),
            key=f"trainee_section_{case['id']}_{section['section_key']}",
            on_change="rerun",
            icon=icon,
        )
        if not panel.open:
            continue
        with panel:
            if not corrections:
                st.success(
                    "No corrections for this section.",
                    icon=":material/check_circle:",
                )
                continue
            for correction_index, correction in enumerate(corrections, start=1):
                with st.container(border=True):
                    st.caption(f"Correction {correction_index}")
                    _correction_badge(str(correction.get("status") or "open"))
                    st.write(correction.get("body") or "")
                    _render_screenshots(
                        repository,
                        correction.get("correction_screenshots") or [],
                        key_prefix=f"trainee_corr_{correction['id']}",
                    )
