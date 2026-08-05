"""Revision and correction-thread UI for trainer and trainee portals."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from html import escape
from typing import Any, Literal

import streamlit as st
from postgrest.exceptions import APIError

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

RELATED_FILE_LABELS: dict[str, str] = {
    "pdf1": "PDF 1",
    "pdf2": "PDF 2",
    "ov": "OV",
}
RELATED_FILE_GROUPS: tuple[tuple[str | None, str], ...] = (
    ("pdf1", "PDF 1"),
    ("pdf2", "PDF 2"),
    ("ov", "OV"),
    (None, "Not file-specific"),
)

_CORRECTION_ZONE_CSS = """
<style>
/* Notebook page shells — glow stays on the bordered container only */
div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > div > .ct-zone-needs),
div[data-testid="stVerticalBlockBorderWrapper"]:has(.ct-zone-needs) {
  border-color: rgba(251, 146, 60, 0.4) !important;
  background:
    linear-gradient(
      180deg,
      rgba(251, 146, 60, 0.10) 0%,
      rgba(23, 32, 51, 0.55) 7rem,
      rgba(23, 32, 51, 0.35) 100%
    );
  box-shadow:
    0 0 0 1px rgba(251, 146, 60, 0.18),
    0 12px 28px rgba(15, 23, 42, 0.35);
  border-radius: 1rem;
  padding-top: 0.15rem;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > div > .ct-zone-ok),
div[data-testid="stVerticalBlockBorderWrapper"]:has(.ct-zone-ok) {
  border-color: rgba(34, 197, 94, 0.35) !important;
  background:
    linear-gradient(
      180deg,
      rgba(34, 197, 94, 0.09) 0%,
      rgba(23, 32, 51, 0.55) 7rem,
      rgba(23, 32, 51, 0.35) 100%
    );
  box-shadow:
    0 0 0 1px rgba(34, 197, 94, 0.16),
    0 12px 28px rgba(15, 23, 42, 0.32);
  border-radius: 1rem;
  padding-top: 0.15rem;
}

/* Section headings inside the notebook */
.ct-nb-section {
  font-size: 1.02rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  margin: 1rem 0 0.4rem;
  padding: 0.15rem 0 0.45rem;
  border-bottom: 1px dashed rgba(148, 163, 184, 0.28);
}
.ct-nb-section.needs { color: #fdba74; }
.ct-nb-section.ok { color: #86efac; }
.ct-nb-section .ct-nb-meta {
  font-weight: 500;
  opacity: 0.7;
  font-size: 0.82rem;
  margin-left: 0.4rem;
  letter-spacing: 0;
}

/* Note cards — accent only on the card, never the notebook page shell */
div[data-testid="stVerticalBlockBorderWrapper"]:has(.ct-nb-note-needs):not(
  :has(.ct-zone-needs)
):not(:has(.ct-zone-ok)) {
  border-left: 3px solid #fb923c !important;
  background: rgba(15, 23, 42, 0.28);
  border-radius: 0.65rem;
  box-shadow: none;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.ct-nb-note-ok):not(
  :has(.ct-zone-needs)
):not(:has(.ct-zone-ok)) {
  border-left: 3px solid #4ade80 !important;
  background: rgba(15, 23, 42, 0.18);
  border-radius: 0.65rem;
  box-shadow: none;
}
</style>
"""


def _inject_correction_zone_styles() -> None:
    st.markdown(_CORRECTION_ZONE_CSS, unsafe_allow_html=True)


@contextmanager
def _correction_zone(
    kind: Literal["needs", "ok"],
    *,
    title: str,
    detail: str,
) -> Iterator[None]:
    """Notebook page shell — orange for open work, green for passed sections."""
    _inject_correction_zone_styles()
    marker = "ct-zone-needs" if kind == "needs" else "ct-zone-ok"
    accent = "orange" if kind == "needs" else "green"
    icon = (
        ":material/edit_note:" if kind == "needs" else ":material/check_circle:"
    )
    with st.container(border=True):
        st.markdown(f'<span class="{marker}"></span>', unsafe_allow_html=True)
        st.markdown(f"{icon} **:{accent}[{title}]**")
        st.caption(detail)
        yield


def _cascade_section_title(
    title: str,
    *,
    kind: Literal["needs", "ok"],
    count_label: str | None = None,
) -> None:
    meta = (
        f'<span class="ct-nb-meta">{escape(count_label)}</span>'
        if count_label
        else ""
    )
    st.markdown(
        f'<div class="ct-nb-section {kind}">{escape(title)}{meta}</div>',
        unsafe_allow_html=True,
    )


@contextmanager
def _cascade_indent(*, kind: Literal["needs", "ok"] = "needs") -> Iterator[None]:
    """Keep corrections grouped under a section title (no outer rails)."""
    del kind
    yield


def _open_threads(threads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [thread for thread in threads if thread.get("status") == "open"]


def _related_file_label(value: str | None) -> str | None:
    if not value:
        return None
    return RELATED_FILE_LABELS.get(value)


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
    open_count: int = 0,
    resolved_count: int = 0,
) -> None:
    """Compact horizontal file strip — open links + optional replace flag."""
    rows = _sorted_requirements(requirements)
    if not rows:
        return

    pills, summary = st.columns([3, 1], vertical_alignment="center")
    with pills:
        cols = st.columns(max(len(rows), 1))
        for col, requirement in zip(cols, rows, strict=False):
            with col:
                label = FILE_KIND_LABELS.get(requirement["kind"], requirement["kind"])
                url = requirement.get("external_url") or ""
                req_id = str(requirement["id"])
                flag_key = f"draft_replace_{case_id}_{req_id}"
                if (
                    flag_key not in st.session_state
                    and requirement["status"] == "replacement_requested"
                ):
                    st.session_state[flag_key] = True
                flagged = bool(st.session_state.get(flag_key, False))
                if url:
                    st.link_button(
                        f":material/description: {label}",
                        url,
                        width="stretch",
                        type="secondary",
                    )
                else:
                    st.caption(f":material/description: {label}")
                if editable and requirement["status"] != "accepted":
                    st.toggle(
                        "Needs replacement",
                        key=flag_key,
                        help="Flag this file for replacement on publish",
                    )
                    if flagged:
                        st.text_input(
                            "Why",
                            key=f"draft_replace_note_{case_id}_{req_id}",
                            placeholder="Optional note",
                            label_visibility="collapsed",
                        )
                elif flagged:
                    st.caption(":orange[Replace pending]")
    with summary:
        if open_count:
            st.markdown(
                f":orange[**{open_count}** open] · "
                f":green[**{resolved_count}** resolved]"
            )
        elif resolved_count:
            st.markdown(f":green[**{resolved_count}** resolved]")
        else:
            st.caption("No corrections yet")


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
                    if is_draft and revision_id is not None and open_threads:
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
    _clear_section_overrides()
    status = case["status"]
    requirements = _sorted_requirements(
        repository.list_requirements_for_case(case["id"])
    )
    revisions = repository.list_revisions_for_case(case["id"])
    threads = repository.list_correction_threads(case["id"])
    open_thread_count = len(_open_threads(threads))
    resolved_count = len(threads) - open_thread_count
    draft = next((row for row in revisions if row["status"] == "draft"), None)
    can_edit_files = status in {"in_review", "corrections_sent"}

    def _files(*, editable: bool) -> None:
        _render_file_draft_panel(
            requirements,
            case_id=case["id"],
            editable=editable,
            open_count=open_thread_count,
            resolved_count=resolved_count,
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
            _files(editable=can_edit_files)
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
        _files(editable=can_edit_files)
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

    _files(editable=is_draft or can_edit_files)

    revision_no_by_id = {row["id"]: row["revision_no"] for row in revisions}
    can_act = is_draft or can_edit_files
    _render_corrections_workspace(
        repository,
        user_id=user_id,
        case_id=case["id"],
        threads=threads,
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
    """Patch thread lists locally so a fragment-scoped rerun shows changes."""
    fresh = repository.list_correction_threads(case_id)
    st.session_state[f"_threads_override_{case_id}"] = fresh
    for section_key, _label, _order in REVIEW_SECTIONS:
        st.session_state[_section_override_key(case_id, section_key)] = [
            thread for thread in fresh if thread.get("section") == section_key
        ]


def _clear_section_overrides() -> None:
    """Drop stale in-fragment patches on every real full-page load."""
    prefixes = ("_section_override_", "_threads_override_")
    for key in [k for k in st.session_state if k.startswith(prefixes)]:
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


def _thread_body(thread: dict[str, Any]) -> str:
    events = thread.get("correction_events") or []
    raised = next(
        (event for event in events if event.get("event_type") == "raised"),
        None,
    )
    return str((raised or {}).get("body") or "")


def _render_thread_attach_controls(
    repository: TrainingRepository,
    *,
    user_id: str,
    case_id: str,
    thread: dict[str, Any],
) -> None:
    """Screenshot attach — popover so it does not nest another bordered box."""
    with st.popover(
        "Screenshots",
        icon=":material/image:",
        help="Paste or upload screenshots for this correction",
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
        if not draft.submitted:
            return
        images = list(draft.images) + list(disk_images)
        if not images:
            st.warning("Paste or upload a screenshot first.")
            return
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


def _render_thread_card(
    repository: TrainingRepository,
    *,
    user_id: str,
    case_id: str,
    thread: dict[str, Any],
    can_act: bool,
    revision_id: str | None,
    revision_no_by_id: dict[str, int],
    show_section_in_caption: bool = True,
    bordered: bool | None = None,
) -> None:
    """One correction. Open items get a single card border; resolved stay flat."""
    status = str(thread.get("status") or "open")
    body = _thread_body(thread)
    caption, persisted = _thread_history_caption(
        thread,
        revision_no_by_id=revision_no_by_id,
    )
    file_label = _related_file_label(thread.get("related_file"))
    if show_section_in_caption:
        section_bit = section_label(str(thread.get("section") or ""))
        caption = f"{section_bit} · {caption}" if caption else section_bit

    use_border = bordered if bordered is not None else status == "open"
    with st.container(border=use_border):
        if use_border:
            note_kind = "needs" if status == "open" else "ok"
            st.markdown(
                f'<span class="ct-nb-note-{note_kind}"></span>',
                unsafe_allow_html=True,
            )
        head = st.columns([3, 1], vertical_alignment="center")
        with head[0]:
            with st.container(horizontal=True, gap="small"):
                _thread_status_badge(status)
                if file_label:
                    st.badge(
                        file_label,
                        icon=":material/description:",
                        color="gray",
                    )
                if persisted >= 2 and status == "open":
                    st.badge(
                        f"{persisted} revs",
                        icon=":material/sync:",
                        color="orange",
                    )
        with head[1]:
            if can_act and status == "open":
                if st.button(
                    "Mark resolved",
                    key=f"resolve_thread_{thread['id']}",
                    width="stretch",
                    type="primary",
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

        st.markdown(body)
        if caption:
            st.caption(caption)
        _render_screenshots(
            repository,
            thread.get("correction_thread_screenshots") or [],
            key_prefix=f"thread_{thread['id']}",
        )

        if can_act and status == "open":
            _render_thread_attach_controls(
                repository,
                user_id=user_id,
                case_id=case_id,
                thread=thread,
            )


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
    key_prefix: str = "",
) -> None:
    options = list(checklist_for_section(section_key))
    composer_key = f"{key_prefix}{case_id}_{section_key}"

    st.caption(
        "Checklist clicks stay in this box — the rest of the page will not jump."
    )
    selected = _render_visible_checklist(
        checklist_key=composer_key,
        options=options,
    )
    file_options = ["__none__", "pdf1", "pdf2", "ov"]
    related = st.segmented_control(
        "File",
        options=file_options,
        format_func=lambda value: (
            "Not file-specific" if value == "__none__" else RELATED_FILE_LABELS[value]
        ),
        default="__none__",
        key=f"related_file_{composer_key}",
        label_visibility="collapsed",
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

    related_file = None if not related or related == "__none__" else related
    created_ids: list[str] = []
    try:
        for body in bodies:
            thread_id = repository.create_correction_thread(
                case_id=case_id,
                section=section_key,
                body=body,
                revision_id=revision_id,
                related_file=related_file,
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


def _render_add_correction_control(
    repository: TrainingRepository,
    *,
    user_id: str,
    case_id: str,
    section_key: str,
    revision_id: str | None,
    label: str = "Add correction",
    key_suffix: str = "",
) -> None:
    """Compact add entry — popover, not another nested bordered box."""
    with st.popover(
        label,
        icon=":material/add:",
        key=f"add_corr_pop_{case_id}_{section_key}_{key_suffix}",
    ):
        _render_section_composer(
            repository,
            user_id=user_id,
            case_id=case_id,
            section_key=section_key,
            revision_id=revision_id,
            key_prefix=f"{key_suffix}_",
        )


@st.fragment
def _render_global_add_correction(
    repository: TrainingRepository,
    *,
    user_id: str,
    case_id: str,
    revision_id: str | None,
) -> None:
    """Toolbar '+ Add correction' — pick a section, then compose."""
    with st.popover(
        "Add correction",
        icon=":material/add:",
        key=f"global_add_corr_{case_id}",
    ):
        section_keys = [key for key, _label, _order in REVIEW_SECTIONS]
        section_key = st.selectbox(
            "Section",
            options=section_keys,
            format_func=section_label,
            key=f"global_add_section_{case_id}",
        )
        _render_section_composer(
            repository,
            user_id=user_id,
            case_id=case_id,
            section_key=str(section_key),
            revision_id=revision_id,
            key_prefix="global_",
        )


def _render_corrections_workspace(
    repository: TrainingRepository,
    *,
    user_id: str,
    case_id: str,
    threads: list[dict[str, Any]],
    can_act: bool,
    revision_id: str | None,
    revision_no_by_id: dict[str, int],
) -> None:
    """Open work first; passed sections collapse into a green rollup."""
    override = st.session_state.get(f"_threads_override_{case_id}")
    live_threads = override if override is not None else threads

    toggle_col, add_col = st.columns([3, 1], vertical_alignment="center")
    with toggle_col:
        view = st.segmented_control(
            "Group corrections",
            options=["section", "file"],
            format_func=lambda value: (
                "By section" if value == "section" else "By file"
            ),
            default="section",
            key=f"corr_view_{case_id}",
            label_visibility="collapsed",
        )
    with add_col:
        if can_act:
            _render_global_add_correction(
                repository,
                user_id=user_id,
                case_id=case_id,
                revision_id=revision_id,
            )

    if view is None:
        view = "section"

    open_threads = _open_threads(live_threads)

    if view == "file":
        _render_corrections_by_file(
            repository,
            user_id=user_id,
            case_id=case_id,
            open_threads=open_threads,
            all_threads=live_threads,
            can_act=can_act,
            revision_id=revision_id,
            revision_no_by_id=revision_no_by_id,
        )
        return

    _render_corrections_by_section(
        repository,
        user_id=user_id,
        case_id=case_id,
        live_threads=live_threads,
        can_act=can_act,
        revision_id=revision_id,
        revision_no_by_id=revision_no_by_id,
    )


def _render_corrections_by_section(
    repository: TrainingRepository,
    *,
    user_id: str,
    case_id: str,
    live_threads: list[dict[str, Any]],
    can_act: bool,
    revision_id: str | None,
    revision_no_by_id: dict[str, int],
) -> None:
    open_keys: list[str] = []
    passed_keys: list[str] = []
    for section_key, _label, _order in REVIEW_SECTIONS:
        section_threads = [
            t for t in live_threads if t.get("section") == section_key
        ]
        if _open_threads(section_threads):
            open_keys.append(section_key)
        else:
            passed_keys.append(section_key)

    open_count = sum(
        len(
            _open_threads(
                [t for t in live_threads if t.get("section") == key]
            )
        )
        for key in open_keys
    )

    if open_keys:
        with _correction_zone(
            "needs",
            title="Needs improvement",
            detail=(
                f"{open_count} open correction"
                f"{'s' if open_count != 1 else ''} across "
                f"{len(open_keys)} section"
                f"{'s' if len(open_keys) != 1 else ''}"
            ),
        ):
            for section_key in open_keys:
                _render_open_section_panel(
                    repository,
                    user_id=user_id,
                    case_id=case_id,
                    section_key=section_key,
                    threads=[
                        t
                        for t in live_threads
                        if t.get("section") == section_key
                    ],
                    can_act=can_act,
                    revision_id=revision_id,
                    revision_no_by_id=revision_no_by_id,
                )
    else:
        st.success(
            "No open corrections — every section is clear.",
            icon=":material/check_circle:",
        )

    if not passed_keys:
        return

    with _correction_zone(
        "ok",
        title="Looks good",
        detail=(
            f"{len(passed_keys)} section"
            f"{'s' if len(passed_keys) != 1 else ''} clear — "
            "expand a section only to add or reopen"
        ),
    ):
        for section_key in passed_keys:
            _render_passed_section_row(
                repository,
                user_id=user_id,
                case_id=case_id,
                section_key=section_key,
                threads=[
                    t for t in live_threads if t.get("section") == section_key
                ],
                can_act=can_act,
                revision_id=revision_id,
                revision_no_by_id=revision_no_by_id,
            )


def _render_corrections_by_file(
    repository: TrainingRepository,
    *,
    user_id: str,
    case_id: str,
    open_threads: list[dict[str, Any]],
    all_threads: list[dict[str, Any]],
    can_act: bool,
    revision_id: str | None,
    revision_no_by_id: dict[str, int],
) -> None:
    active_groups: list[tuple[str | None, str, list[dict[str, Any]]]] = []
    clear_groups: list[tuple[str | None, str]] = []
    for file_key, label in RELATED_FILE_GROUPS:
        group = [
            thread
            for thread in open_threads
            if (thread.get("related_file") or None) == file_key
        ]
        if group:
            active_groups.append((file_key, label, group))
        else:
            clear_groups.append((file_key, label))

    if active_groups:
        with _correction_zone(
            "needs",
            title="Needs improvement",
            detail=(
                f"{len(open_threads)} open correction"
                f"{'s' if len(open_threads) != 1 else ''} by file"
            ),
        ):
            for _file_key, label, group in active_groups:
                _cascade_section_title(
                    label,
                    kind="needs",
                    count_label=f"{len(group)} open",
                )
                with _cascade_indent():
                    for thread in group:
                        _render_thread_card(
                            repository,
                            user_id=user_id,
                            case_id=case_id,
                            thread=thread,
                            can_act=can_act,
                            revision_id=revision_id,
                            revision_no_by_id=revision_no_by_id,
                            show_section_in_caption=True,
                        )
    else:
        st.success(
            "No open corrections — every file group is clear.",
            icon=":material/check_circle:",
        )

    resolved = [
        thread for thread in all_threads if thread.get("status") != "open"
    ]
    if not clear_groups and not resolved:
        return

    with _correction_zone(
        "ok",
        title="Looks good",
        detail=(
            f"{len(clear_groups)} file group"
            f"{'s' if len(clear_groups) != 1 else ''} clear"
            + (f" · {len(resolved)} resolved" if resolved else "")
        ),
    ):
        if clear_groups:
            for _key, label in clear_groups:
                _cascade_section_title(label, kind="ok", count_label="clear")
        if resolved:
            st.caption("Resolved corrections")
            with _cascade_indent(kind="ok"):
                for thread in resolved:
                    _render_thread_card(
                        repository,
                        user_id=user_id,
                        case_id=case_id,
                        thread=thread,
                        can_act=can_act,
                        revision_id=revision_id,
                        revision_no_by_id=revision_no_by_id,
                        show_section_in_caption=True,
                        bordered=False,
                    )


@st.fragment
def _render_open_section_panel(
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
    """One open section in the needs-improvement cascade."""
    override = st.session_state.get(_section_override_key(case_id, section_key))
    section_threads = override if override is not None else threads
    open_threads = _open_threads(section_threads)
    resolved_threads = [
        thread for thread in section_threads if thread.get("status") != "open"
    ]
    title = section_label(section_key)

    head = st.columns([3, 1], vertical_alignment="center")
    with head[0]:
        _cascade_section_title(
            title,
            kind="needs",
            count_label=(
                f"{len(open_threads)} open"
                if len(open_threads) != 1
                else "1 open"
            ),
        )
    with head[1]:
        if can_act:
            _render_add_correction_control(
                repository,
                user_id=user_id,
                case_id=case_id,
                section_key=section_key,
                revision_id=revision_id,
                label="Add",
                key_suffix="open",
            )

    with _cascade_indent(kind="needs"):
        for thread in open_threads:
            _render_thread_card(
                repository,
                user_id=user_id,
                case_id=case_id,
                thread=thread,
                can_act=can_act,
                revision_id=revision_id,
                revision_no_by_id=revision_no_by_id,
                show_section_in_caption=False,
            )

        if resolved_threads:
            with st.expander(
                f"{len(resolved_threads)} resolved earlier",
                expanded=False,
            ):
                for thread in resolved_threads:
                    _render_thread_card(
                        repository,
                        user_id=user_id,
                        case_id=case_id,
                        thread=thread,
                        can_act=can_act,
                        revision_id=revision_id,
                        revision_no_by_id=revision_no_by_id,
                        show_section_in_caption=False,
                        bordered=False,
                    )


@st.fragment
def _render_passed_section_row(
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
    """Passed section title in the green cascade — history stays collapsed."""
    override = st.session_state.get(_section_override_key(case_id, section_key))
    section_threads = override if override is not None else threads
    resolved_threads = [
        thread for thread in section_threads if thread.get("status") != "open"
    ]
    title = section_label(section_key)
    count_label = (
        f"{len(resolved_threads)} resolved" if resolved_threads else "clear"
    )

    row = st.columns([3, 1], vertical_alignment="center")
    with row[0]:
        _cascade_section_title(title, kind="ok", count_label=count_label)
    with row[1]:
        if can_act:
            _render_add_correction_control(
                repository,
                user_id=user_id,
                case_id=case_id,
                section_key=section_key,
                revision_id=revision_id,
                label="Add",
                key_suffix="passed",
            )

    if resolved_threads:
        with _cascade_indent(kind="ok"):
            with st.expander("History", expanded=False):
                for thread in resolved_threads:
                    _render_thread_card(
                        repository,
                        user_id=user_id,
                        case_id=case_id,
                        thread=thread,
                        can_act=can_act,
                        revision_id=revision_id,
                        revision_no_by_id=revision_no_by_id,
                        show_section_in_caption=False,
                        bordered=False,
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
        st.caption(
            "No published review yet. You can still ask a question above "
            "anytime."
        )
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

    open_sections: list[tuple[str, str, list[dict[str, Any]]]] = []
    passed_sections: list[tuple[str, str, list[dict[str, Any]]]] = []
    for section_key, title, _order in REVIEW_SECTIONS:
        section_threads = [
            thread for thread in threads if thread.get("section") == section_key
        ]
        if not section_threads:
            continue
        if _open_threads(section_threads):
            open_sections.append((section_key, title, section_threads))
        else:
            passed_sections.append((section_key, title, section_threads))

    if open_sections:
        with _correction_zone(
            "needs",
            title="Needs improvement",
            detail=(
                f"{open_count} open item"
                f"{'s' if open_count != 1 else ''} to address"
            ),
        ):
            for _section_key, title, section_threads in open_sections:
                open_list = _open_threads(section_threads)
                resolved_list = [
                    thread
                    for thread in section_threads
                    if thread.get("status") != "open"
                ]
                _cascade_section_title(
                    title,
                    kind="needs",
                    count_label=(
                        f"{len(open_list)} to fix"
                        if len(open_list) != 1
                        else "1 to fix"
                    ),
                )
                with _cascade_indent(kind="needs"):
                    for thread in open_list:
                        with st.container(border=True):
                            st.markdown(
                                '<span class="ct-nb-note-needs"></span>',
                                unsafe_allow_html=True,
                            )
                            _thread_status_badge("open")
                            st.markdown(_thread_body(thread))
                            caption, _persisted = _thread_history_caption(
                                thread,
                                revision_no_by_id=revision_no_by_id,
                            )
                            if caption:
                                st.caption(caption)
                            _render_screenshots(
                                repository,
                                thread.get("correction_thread_screenshots")
                                or [],
                                key_prefix=f"trainee_thread_{thread['id']}",
                            )
                    if resolved_list:
                        with st.expander(
                            f"{len(resolved_list)} resolved in {title}"
                        ):
                            for thread in resolved_list:
                                _thread_status_badge("resolved")
                                st.markdown(_thread_body(thread))
                                caption, _persisted = _thread_history_caption(
                                    thread,
                                    revision_no_by_id=revision_no_by_id,
                                )
                                if caption:
                                    st.caption(caption)

    if passed_sections:
        with _correction_zone(
            "ok",
            title="Looks good",
            detail=(
                f"{len(passed_sections)} section"
                f"{'s' if len(passed_sections) != 1 else ''} clear"
            ),
        ):
            for _section_key, title, section_threads in passed_sections:
                resolved_list = [
                    thread
                    for thread in section_threads
                    if thread.get("status") != "open"
                ]
                _cascade_section_title(
                    title,
                    kind="ok",
                    count_label=(
                        f"{len(resolved_list)} resolved"
                        if resolved_list
                        else "clear"
                    ),
                )
