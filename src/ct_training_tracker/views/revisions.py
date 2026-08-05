"""Revision and correction-thread UI for trainer and trainee portals."""

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
from ct_training_tracker.data_cache import invalidate_trainer_cache
from ct_training_tracker.files import FILE_KIND_LABELS, READY_SLOT_STATUSES
from ct_training_tracker.metrics import open_thread_count_by_section
from ct_training_tracker.repository import TrainingRepository
from ct_training_tracker.revisions import (
    REVIEW_SECTIONS,
    can_start_revision,
    checklist_for_section,
    feedback_bodies,
    section_label,
)
from ct_training_tracker.storage_cache import cached_storage_bytes

KIND_ORDER = ("pdf_primary", "pdf_secondary", "ov")


def _open_threads(threads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [thread for thread in threads if thread.get("status") == "open"]


def _render_feedback_context(
    case: dict[str, Any],
    *,
    threads: list[dict[str, Any]],
) -> None:
    """Repeat critical case identity inside Feedback to prevent mix-ups."""
    open_count = len(_open_threads(threads))
    resolved_count = len(threads) - open_count
    with st.container(border=True, horizontal=True, vertical_alignment="center"):
        with st.container():
            st.caption("Currently reviewing")
            st.markdown(f"**{case.get('trainee_name') or 'Trainee'}**")
        with st.container():
            st.caption("Case")
            st.markdown(f"**{case_title(case)}**")
        with st.container():
            st.caption("Corrections")
            if not threads:
                st.markdown("_None raised yet_")
            elif open_count:
                st.markdown(
                    f":orange[{open_count} open] · :green[{resolved_count} resolved]"
                )
            else:
                st.markdown(f":green[All {resolved_count} resolved]")


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
    open_threads: int = 0,
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
        if open_threads:
            parts.append(f"{open_threads} correction(s) still open")
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
                    if revision_id is not None and open_threads:
                        repository.mark_open_threads_still_open(
                            case_id=case["id"],
                            revision_id=revision_id,
                        )
                except APIError as exc:
                    st.error(exc.message)
                else:
                    invalidate_trainer_cache()
                    st.toast("Review published")
                    st.rerun()
        with approve_col:
            approve_blocked = bool(decisions) or open_threads > 0
            if open_threads:
                block_reason = (
                    f"{open_threads} correction(s) still open — resolve them first."
                )
            else:
                block_reason = (
                    "Accepts all files and closes the case. "
                    "Clear replacement marks first."
                )
            if st.button(
                "Approve case",
                key=f"approve_case_{case['id']}",
                width="stretch",
                icon=":material/check_circle:",
                disabled=approve_blocked,
                help=block_reason,
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
                    invalidate_trainer_cache()
                    st.toast("Case approved")
                    st.rerun()


def _sync_revision_choice(
    widget_key: str,
    revisions: list[dict[str, Any]],
) -> None:
    """Keep the revision selector honest across reruns.

    Clears the stored selectbox choice when the revision list changes (a new
    revision appeared) so the selector snaps back to the newest revision, and
    drops stale choices that no longer match an existing revision.
    """
    count_key = f"{widget_key}__count"
    valid_ids = {row["id"] for row in revisions}
    if st.session_state.get(count_key) != len(revisions):
        st.session_state[count_key] = len(revisions)
        st.session_state.pop(widget_key, None)
    elif (
        widget_key in st.session_state
        and st.session_state[widget_key] not in valid_ids
    ):
        st.session_state.pop(widget_key, None)


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
    threads = repository.list_correction_threads(case["id"])
    open_thread_count = len(_open_threads(threads))
    draft = next((row for row in revisions if row["status"] == "draft"), None)
    can_edit_files = status in {"in_review", "corrections_sent"}
    _render_feedback_context(case, threads=threads)

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
                open_threads=open_thread_count,
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
            open_threads=open_thread_count,
        )
        return

    labels = {
        row["id"]: f"Revision {row['revision_no']} · {row['status']}"
        for row in revisions
    }
    default_id = draft["id"] if draft else revisions[0]["id"]
    options = list(labels)
    index = options.index(default_id) if default_id in labels else 0

    widget_key = f"trainer_revision_{case['id']}"
    _sync_revision_choice(widget_key, revisions)
    revision_id = st.selectbox(
        "Revision",
        options=options,
        index=index,
        format_func=lambda value: labels[value],
        key=widget_key,
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
        "One card per correction. Resolve a card when the trainee fixes it."
    )
    _render_thread_chips(threads)

    revision_no_by_id = {row["id"]: row["revision_no"] for row in revisions}
    can_act = is_draft or can_edit_files
    for section_key, _label, _order in REVIEW_SECTIONS:
        _render_section_thread_panel(
            repository,
            user_id=user_id,
            case_id=case["id"],
            section_key=section_key,
            threads=[t for t in threads if t.get("section") == section_key],
            can_act=can_act,
            revision_id=revision_id,
            revision_no_by_id=revision_no_by_id,
        )

    _render_publish_action_bar(
        repository,
        case=case,
        revision_id=revision_id,
        requirements=requirements,
        is_draft=is_draft,
        open_threads=open_thread_count,
    )


def _upload_thread_images(
    repository: TrainingRepository,
    *,
    user_id: str,
    case_id: str,
    thread_id: str,
    images: list[PastedImage],
) -> None:
    for image in images:
        repository.upload_thread_screenshot(
            user_id=user_id,
            case_id=case_id,
            thread_id=thread_id,
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


def _render_thread_chips(threads: list[dict[str, Any]]) -> None:
    """Needs work / Looks good summary derived from open thread counts."""
    open_by_section = open_thread_count_by_section(threads)
    need_labels = [
        f"{label} ({open_by_section[key]})"
        for key, label, _order in REVIEW_SECTIONS
        if open_by_section.get(key)
    ]
    ok_labels = [
        label
        for key, label, _order in REVIEW_SECTIONS
        if not open_by_section.get(key)
    ]

    top = st.columns([1.2, 1])
    with top[0]:
        st.markdown("**Needs work**")
        if need_labels:
            st.markdown(
                " ".join(f":orange-badge[{label}]" for label in need_labels)
            )
        else:
            st.caption("No open corrections.")
    with top[1]:
        st.markdown("**Looks good**")
        if ok_labels:
            st.markdown(" ".join(f":green-badge[{label}]" for label in ok_labels))
        else:
            st.caption("Every section has open corrections.")


def _thread_status_badge(status: str) -> None:
    if status == "resolved":
        st.badge("Resolved", icon=":material/check_circle:", color="green")
    else:
        st.badge("Open", icon=":material/pending:", color="orange")


def _section_override_key(case_id: str, section_key: str) -> str:
    return f"_section_override_{case_id}_{section_key}"


def _refresh_thread_overrides(repository: TrainingRepository, case_id: str) -> None:
    """Patch every section's thread list locally so a fragment-scoped rerun
    shows the change instantly without reloading the rest of the page."""
    fresh = repository.list_correction_threads(case_id)
    for section_key, _label, _order in REVIEW_SECTIONS:
        st.session_state[_section_override_key(case_id, section_key)] = [
            thread for thread in fresh if thread.get("section") == section_key
        ]


def _clear_section_overrides() -> None:
    """Drop stale in-fragment patches on every real full-page load, since
    the freshly fetched thread data becomes authoritative again."""
    prefix = "_section_override_"
    for key in [k for k in st.session_state if k.startswith(prefix)]:
        del st.session_state[key]


def _thread_history_caption(
    thread: dict[str, Any],
    *,
    revision_no_by_id: dict[str, int],
) -> tuple[str, int]:
    """(caption, persisted revision count) for one thread."""
    events = thread.get("correction_events") or []
    touched_ids = {
        str(event["revision_id"])
        for event in events
        if event.get("revision_id")
    }
    persisted = len(touched_ids)
    touched = sorted(
        {
            revision_no_by_id[revision_id]
            for revision_id in touched_ids
            if revision_id in revision_no_by_id
        }
    )
    if not touched:
        return ("", persisted)
    first = touched[0]
    last = touched[-1]
    if thread.get("status") == "resolved":
        resolved_no = revision_no_by_id.get(
            str(thread.get("resolved_in_revision_id") or "")
        )
        if resolved_no is not None:
            return (
                f"Raised in revision {first} · resolved in revision {resolved_no}",
                persisted,
            )
        return (f"Raised in revision {first}", persisted)
    if last != first:
        return (
            f"Raised in revision {first} · still open in revision {last}",
            persisted,
        )
    return (f"Raised in revision {first}", persisted)


def _render_thread_card(
    repository: TrainingRepository,
    *,
    user_id: str,
    case_id: str,
    thread: dict[str, Any],
    can_act: bool,
    revision_id: str | None,
    revision_no_by_id: dict[str, int],
) -> None:
    status = str(thread.get("status") or "open")
    events = thread.get("correction_events") or []
    raised = next(
        (event for event in events if event.get("event_type") == "raised"),
        None,
    )
    body = (raised or {}).get("body") or ""
    caption, persisted = _thread_history_caption(
        thread,
        revision_no_by_id=revision_no_by_id,
    )

    with st.container(border=True):
        head = st.columns([1.4, 1], vertical_alignment="center")
        with head[0]:
            _thread_status_badge(status)
            if persisted >= 2:
                st.caption(f":material/sync: Persisted {persisted} revisions")
        with head[1]:
            if can_act and status == "open":
                if st.button(
                    "Mark resolved",
                    key=f"resolve_thread_{thread['id']}",
                    width="stretch",
                ):
                    try:
                        repository.resolve_thread(thread["id"], revision_id)
                    except APIError as exc:
                        st.error(exc.message)
                    else:
                        _refresh_thread_overrides(repository, case_id)
                        st.toast("Marked resolved")
                        st.rerun(scope="fragment")
            elif can_act and status == "resolved":
                if st.button(
                    "Reopen",
                    key=f"reopen_thread_{thread['id']}",
                    width="stretch",
                ):
                    try:
                        repository.reopen_thread(thread["id"], revision_id)
                    except APIError as exc:
                        st.error(exc.message)
                    else:
                        _refresh_thread_overrides(repository, case_id)
                        st.toast("Reopened")
                        st.rerun(scope="fragment")

        st.write(body)
        if caption:
            st.caption(caption)
        _render_screenshots(
            repository,
            thread.get("correction_thread_screenshots") or [],
            key_prefix=f"thread_{thread['id']}",
        )

        if not can_act or status != "open":
            return

        with st.expander(
            "Add screenshots",
            icon=":material/image:",
        ):
            draft_key = f"comment_attach_{thread['id']}"
            draft = comment_box(
                key=draft_key,
                placeholder="Paste screenshots here (Ctrl+V / Cmd+V)",
                submit_label="Save screenshots",
            )
            disk_images = _render_optional_upload(
                upload_key=f"shot_{thread['id']}",
            )
            if draft.submitted:
                images = list(draft.images) + list(disk_images)
                if not images:
                    st.warning("Paste or upload a screenshot first.")
                else:
                    try:
                        _upload_thread_images(
                            repository,
                            user_id=user_id,
                            case_id=case_id,
                            thread_id=thread["id"],
                            images=images,
                        )
                    except (APIError, ValueError, Exception) as exc:
                        message = getattr(exc, "message", None) or str(exc)
                        st.error(message)
                    else:
                        clear_comment_draft(draft_key)
                        _refresh_thread_overrides(repository, case_id)
                        st.toast(f"Attached {len(images)} screenshot(s)")
                        st.rerun(scope="fragment")


def _render_visible_checklist(
    *,
    checklist_key: str,
    options: list[str],
) -> list[str]:
    selected: list[str] = []
    if not options:
        return selected
    st.caption("Check only what needs fixing. Leave blank if this section is OK.")
    for index, item in enumerate(options):
        if st.checkbox(item, key=f"check_{checklist_key}_{index}"):
            selected.append(item)
    return selected


def _render_section_composer(
    repository: TrainingRepository,
    *,
    user_id: str,
    case_id: str,
    section_key: str,
    revision_id: str | None,
) -> None:
    options = list(checklist_for_section(section_key))
    composer_key = f"{case_id}_{section_key}"

    st.caption(
        "Checklist clicks stay in this box — the rest of the page will not jump."
    )
    selected = _render_visible_checklist(
        checklist_key=composer_key,
        options=options,
    )
    st.markdown("**Comment + screenshots**")
    draft_key = f"section_comment_{composer_key}"
    draft = comment_box(
        key=draft_key,
        placeholder="Notes… paste screenshots with Ctrl+V / Cmd+V",
        submit_label="Save feedback",
    )
    disk_images = _render_optional_upload(
        upload_key=f"pending_shots_{composer_key}",
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
            thread_id = repository.create_correction_thread(
                case_id=case_id,
                section=section_key,
                body=body,
                revision_id=revision_id,
            )
            created_ids.append(thread_id)
        if shots and created_ids:
            target_id = (
                created_ids[-1]
                if draft.text.strip() or len(bodies) == 1
                else created_ids[0]
            )
            _upload_thread_images(
                repository,
                user_id=user_id,
                case_id=case_id,
                thread_id=target_id,
                images=shots,
            )
    except (APIError, ValueError, Exception) as exc:
        message = getattr(exc, "message", None) or str(exc)
        st.error(message)
        return

    clear_comment_draft(draft_key)
    _refresh_thread_overrides(repository, case_id)
    st.toast(f"Saved {len(created_ids)} correction(s)")
    st.rerun(scope="fragment")


@st.fragment
def _render_section_thread_panel(
    repository: TrainingRepository,
    *,
    user_id: str,
    case_id: str,
    section_key: str,
    threads: list[dict[str, Any]],
    can_act: bool,
    revision_id: str | None,
    revision_no_by_id: dict[str, int],
) -> None:
    """One section: header + one card per open thread + resolved rollup +
    composer, as a self-contained fragment so saving/resolving reruns only
    this section and the page never jumps."""
    override = st.session_state.get(_section_override_key(case_id, section_key))
    section_threads = override if override is not None else threads
    open_threads = _open_threads(section_threads)
    resolved_threads = [
        thread for thread in section_threads if thread.get("status") != "open"
    ]

    with st.container(border=True):
        head = st.columns([2, 1], vertical_alignment="center")
        head[0].markdown(f"**{section_label(section_key)}**")
        with head[1]:
            if open_threads:
                st.badge(f"{len(open_threads)} open", color="orange")
            else:
                st.caption("No open corrections")

        for thread in open_threads:
            _render_thread_card(
                repository,
                user_id=user_id,
                case_id=case_id,
                thread=thread,
                can_act=can_act,
                revision_id=revision_id,
                revision_no_by_id=revision_no_by_id,
            )

        if resolved_threads:
            with st.expander(f"{len(resolved_threads)} resolved"):
                for thread in resolved_threads:
                    _render_thread_card(
                        repository,
                        user_id=user_id,
                        case_id=case_id,
                        thread=thread,
                        can_act=can_act,
                        revision_id=revision_id,
                        revision_no_by_id=revision_no_by_id,
                    )

        if can_act:
            with st.expander("Add correction", icon=":material/add:"):
                _render_section_composer(
                    repository,
                    user_id=user_id,
                    case_id=case_id,
                    section_key=section_key,
                    revision_id=revision_id,
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
    threads = repository.list_correction_threads(case["id"])
    if not revisions and not threads:
        st.caption("No published review yet.")
        return

    revision_no_by_id = {row["id"]: row["revision_no"] for row in revisions}
    open_by_section = open_thread_count_by_section(threads)
    open_count = len(_open_threads(threads))

    meta = st.columns([1, 1, 1])
    meta[0].metric("Open items", open_count)
    meta[1].metric("Sections to fix", len(open_by_section))
    meta[2].metric("Sections OK", len(REVIEW_SECTIONS) - len(open_by_section))

    _render_thread_chips(threads)

    st.markdown("#### Feedback by section")
    if not open_count:
        st.success(
            "No open corrections — this package looks good.",
            icon=":material/check_circle:",
        )

    for section_key, title, _order in REVIEW_SECTIONS:
        section_threads = [
            thread for thread in threads if thread.get("section") == section_key
        ]
        open_threads = _open_threads(section_threads)
        resolved_threads = [
            thread
            for thread in section_threads
            if thread.get("status") != "open"
        ]
        if not section_threads:
            continue

        with st.container(border=True):
            head = st.columns([2, 1], vertical_alignment="center")
            head[0].markdown(f"**{title}**")
            with head[1]:
                if open_threads:
                    st.badge(f"{len(open_threads)} to fix", color="orange")
                else:
                    st.badge("Resolved", color="green")

            for thread in open_threads:
                with st.container(border=True):
                    _thread_status_badge("open")
                    events = thread.get("correction_events") or []
                    raised = next(
                        (
                            event
                            for event in events
                            if event.get("event_type") == "raised"
                        ),
                        None,
                    )
                    st.write((raised or {}).get("body") or "")
                    caption, _persisted = _thread_history_caption(
                        thread,
                        revision_no_by_id=revision_no_by_id,
                    )
                    if caption:
                        st.caption(caption)
                    _render_screenshots(
                        repository,
                        thread.get("correction_thread_screenshots") or [],
                        key_prefix=f"trainee_thread_{thread['id']}",
                    )

            if resolved_threads:
                with st.expander(f"{len(resolved_threads)} resolved"):
                    for thread in resolved_threads:
                        with st.container(border=True):
                            _thread_status_badge("resolved")
                            events = thread.get("correction_events") or []
                            raised = next(
                                (
                                    event
                                    for event in events
                                    if event.get("event_type") == "raised"
                                ),
                                None,
                            )
                            st.write((raised or {}).get("body") or "")
                            caption, _persisted = _thread_history_caption(
                                thread,
                                revision_no_by_id=revision_no_by_id,
                            )
                            if caption:
                                st.caption(caption)
