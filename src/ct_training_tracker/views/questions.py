"""Trainee questions and trainer inbox UI."""

from __future__ import annotations

from typing import Any

import streamlit as st
from postgrest.exceptions import APIError

from ct_training_tracker.components.paste_image import (
    PastedImage,
    clear_comment_draft,
    comment_box,
)
from ct_training_tracker.questions import (
    count_open_questions,
    question_section_label,
    question_status_label,
    section_options,
)
from ct_training_tracker.repository import TrainingRepository
from ct_training_tracker.routing import set_query


def _render_question_screenshots(
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

    visible = [(shot, data) for shot, data, _error in loaded if data is not None]
    if visible:
        cols = st.columns(min(4, len(visible)))
        for col, (_shot, data) in zip(cols, visible, strict=False):
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


def _status_badge(status: str) -> None:
    if status == "resolved":
        st.badge("Resolved", icon=":material/check_circle:", color="green")
    elif status == "answered":
        st.badge("Answered", icon=":material/mark_chat_read:", color="blue")
    else:
        st.badge("Open", icon=":material/help:", color="orange")


def _upload_question_images(
    repository: TrainingRepository,
    *,
    user_id: str,
    case_id: str,
    question_id: str,
    images: list[PastedImage],
) -> None:
    for image in images:
        repository.upload_question_screenshot(
            user_id=user_id,
            case_id=case_id,
            question_id=question_id,
            filename=image.filename,
            content=image.content,
            mime_type=image.mime_type,
        )


def render_trainee_questions(
    repository: TrainingRepository,
    *,
    user_id: str,
    case: dict[str, Any],
) -> None:
    st.subheader("Questions")
    if case["status"] == "not_started":
        st.caption("Questions unlock after the case is assigned.")
        return

    questions = repository.list_questions_for_case(case["id"])
    open_count = count_open_questions(questions)
    answered = sum(1 for row in questions if row.get("status") == "answered")
    metrics = st.columns(3)
    metrics[0].metric("Open", open_count)
    metrics[1].metric("Answered", answered)
    metrics[2].metric("Total", len(questions))

    with st.container(border=True):
        st.markdown("**Ask a question**")
        options = section_options()
        labels = {
            (key or "__general__"): label for key, label in options
        }
        keys = [key or "__general__" for key, _label in options]
        selected = st.selectbox(
            "Context",
            options=keys,
            format_func=lambda value: labels[value],
            key=f"q_section_{case['id']}",
        )
        section_key = None if selected == "__general__" else selected
        draft_key = f"ask_question_{case['id']}"
        draft = comment_box(
            key=draft_key,
            placeholder="What do you need help with? Paste screenshots with Ctrl+V",
        )
        if st.button(
            "Send question",
            key=f"send_question_{case['id']}",
            type="primary",
            width="stretch",
            icon=":material/send:",
        ):
            body = draft.text.strip()
            if not body and not draft.images:
                st.warning("Write a question or paste a screenshot.")
            else:
                try:
                    question_id = repository.ask_question(
                        case_id=case["id"],
                        body=body or "See attached screenshot(s).",
                        section_key=section_key,
                    )
                    if draft.images:
                        _upload_question_images(
                            repository,
                            user_id=user_id,
                            case_id=case["id"],
                            question_id=question_id,
                            images=list(draft.images),
                        )
                except (APIError, ValueError, Exception) as exc:
                    message = getattr(exc, "message", None) or str(exc)
                    st.error(message)
                else:
                    clear_comment_draft(draft_key)
                    st.toast("Question sent")
                    st.rerun()

    if not questions:
        st.caption("No questions on this case yet.")
        return

    st.markdown("#### Thread")
    for question in questions:
        status = str(question.get("status") or "open")
        title = (
            f"{question_section_label(question.get('section_key'))} · "
            f"{question_status_label(status)}"
        )
        with st.expander(title, expanded=status != "resolved"):
            _status_badge(status)
            st.write(question.get("body") or "")
            _render_question_screenshots(
                repository,
                question.get("question_screenshots") or [],
                key_prefix=f"tq_{question['id']}",
            )
            if question.get("answer_body"):
                st.markdown("**Trainer answer**")
                st.write(question["answer_body"])
                if question.get("answered_at"):
                    st.caption(f"Answered {question['answered_at']}")

            actions = st.columns(2)
            if status == "answered":
                if actions[0].button(
                    "Mark resolved",
                    key=f"resolve_q_{question['id']}",
                ):
                    try:
                        repository.set_question_status(question["id"], "resolved")
                    except APIError as exc:
                        st.error(exc.message)
                    else:
                        st.toast("Question resolved")
                        st.rerun()
            elif status == "resolved":
                if actions[0].button(
                    "Reopen",
                    key=f"reopen_q_{question['id']}",
                ):
                    try:
                        repository.set_question_status(question["id"], "open")
                    except APIError as exc:
                        st.error(exc.message)
                    else:
                        st.toast("Question reopened")
                        st.rerun()


def render_trainer_question_inbox(repository: TrainingRepository) -> None:
    st.subheader("Question inbox")
    rows = repository.list_open_questions()
    if not rows:
        st.success("No open questions.", icon=":material/check_circle:")
        return

    for row in rows:
        case = row.get("cases") if isinstance(row.get("cases"), dict) else {}
        trainee = case.get("trainees") if isinstance(case.get("trainees"), dict) else {}
        trainee_name = trainee.get("full_name") or "Trainee"
        set_no = case.get("set_no")
        case_no = case.get("case_no")
        title = (
            f"{trainee_name} · Set {set_no} Case {case_no} · "
            f"{question_section_label(row.get('section_key'))}"
        )
        with st.container(border=True):
            st.markdown(f"**{title}**")
            st.write(row.get("body") or "")
            st.caption(str(row.get("created_at") or ""))
            cols = st.columns([1, 1])
            if cols[0].button(
                "Open case",
                key=f"open_q_case_{row['id']}",
                width="stretch",
            ):
                set_query(trainee=case.get("trainee_id"), case=row.get("case_id"))
                st.switch_page("app_pages/trainer_cases.py")
            if cols[1].button(
                "Jump to answer",
                key=f"jump_q_{row['id']}",
                width="stretch",
                type="primary",
            ):
                set_query(trainee=case.get("trainee_id"), case=row.get("case_id"))
                st.session_state["focus_question_id"] = row["id"]
                st.switch_page("app_pages/trainer_cases.py")


def render_trainer_case_questions(
    repository: TrainingRepository,
    *,
    user_id: str,
    case: dict[str, Any],
) -> None:
    del user_id
    st.subheader("Questions")
    questions = repository.list_questions_for_case(case["id"])
    focus_id = st.session_state.pop("focus_question_id", None)

    if not questions:
        st.caption("No questions from the trainee on this case.")
        return

    open_count = count_open_questions(questions)
    st.caption(f"{open_count} open · {len(questions)} total")

    for question in questions:
        status = str(question.get("status") or "open")
        expanded = focus_id == question["id"] or status == "open"
        title = (
            f"{question_section_label(question.get('section_key'))} · "
            f"{question_status_label(status)}"
        )
        with st.expander(title, expanded=expanded):
            _status_badge(status)
            st.write(question.get("body") or "")
            _render_question_screenshots(
                repository,
                question.get("question_screenshots") or [],
                key_prefix=f"trq_{question['id']}",
            )

            if question.get("answer_body"):
                st.markdown("**Your answer**")
                st.write(question["answer_body"])

            if status in {"open", "answered"}:
                answer = st.text_area(
                    "Answer",
                    value=question.get("answer_body") or "",
                    key=f"answer_body_{question['id']}",
                    height=100,
                )
                action_cols = st.columns(2)
                if action_cols[0].button(
                    "Send answer",
                    key=f"answer_q_{question['id']}",
                    type="primary",
                    width="stretch",
                ):
                    try:
                        repository.answer_question(question["id"], answer)
                    except APIError as exc:
                        st.error(exc.message)
                    else:
                        st.toast("Answer sent")
                        st.rerun()
                if status == "answered" and action_cols[1].button(
                    "Mark resolved",
                    key=f"trainer_resolve_q_{question['id']}",
                    width="stretch",
                ):
                    try:
                        repository.set_question_status(question["id"], "resolved")
                    except APIError as exc:
                        st.error(exc.message)
                    else:
                        st.toast("Resolved")
                        st.rerun()
            elif status == "resolved":
                if st.button(
                    "Reopen",
                    key=f"trainer_reopen_q_{question['id']}",
                ):
                    try:
                        repository.set_question_status(question["id"], "open")
                    except APIError as exc:
                        st.error(exc.message)
                    else:
                        st.toast("Reopened")
                        st.rerun()
