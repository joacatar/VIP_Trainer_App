"""Trainee questions and trainer inbox UI."""

from __future__ import annotations

from typing import Any

import streamlit as st
from postgrest.exceptions import APIError

from ct_training_tracker.case_labels import (
    case_catalog_label,
    case_label,
)
from ct_training_tracker.components.paste_image import (
    PastedImage,
    clear_comment_draft,
    comment_box,
)
from ct_training_tracker.questions import (
    count_open_questions,
    count_unread_answers,
    is_unread_answer,
    question_section_label,
    question_status_label,
    section_options,
)
from ct_training_tracker.repository import TrainingRepository
from ct_training_tracker.routing import set_query

STATUS_FILTER_OPTIONS = ("all", "open", "answered", "resolved")


def _render_question_screenshots(
    repository: TrainingRepository,
    screenshots: list[dict[str, Any]],
    *,
    key_prefix: str,
) -> None:
    if not screenshots:
        return

    from ct_training_tracker.storage_cache import cached_storage_bytes

    loaded: list[tuple[dict[str, Any], bytes | None, str | None]] = []
    for shot in screenshots:
        try:
            data = cached_storage_bytes(repository, shot["storage_path"])
            loaded.append((shot, data, None))
        except Exception as exc:
            loaded.append((shot, None, str(exc)))

    visible = [(shot, data) for shot, data, _error in loaded if data is not None]
    if visible:
        cols = st.columns(min(4, len(visible)))
        for index, (col, (shot, data)) in enumerate(
            zip(cols, visible, strict=False)
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


def _case_topic_options() -> list[tuple[str | None, str]]:
    """Topics inside a case: general-to-the-case, then each review section."""
    return [
        (None, "General (this case)"),
        *[
            (key, label)
            for key, label in section_options()
            if key is not None
        ],
    ]


def _anchor_case_for_general(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Pick a case to hang a free-form general question on (schema needs case_id)."""
    preferred = [
        row
        for row in cases
        if str(row.get("status") or "") not in {"approved", "not_started"}
    ]
    return preferred[0] if preferred else cases[0]


def render_home_ask_question(
    repository: TrainingRepository,
    *,
    user_id: str,
    cases: list[dict[str, Any]],
    key_prefix: str = "trainee_home_ask",
) -> None:
    """Ask box: General, or About a case → topic (general-in-case / Scan / …)."""
    eligible = [row for row in cases if str(row.get("status")) != "not_started"]
    if not eligible:
        with st.container(border=True):
            st.markdown("**Ask your trainer**")
            st.caption(
                "Questions unlock once your first case is assigned."
            )
        return

    case_by_id = {str(row["id"]): row for row in eligible}
    with st.container(border=True):
        st.markdown(":material/help: **Ask your trainer**")
        st.caption("Your trainer sees every question in their inbox.")

        kind = st.segmented_control(
            "Question type",
            options=["general", "case"],
            format_func=lambda value: (
                "General" if value == "general" else "About a case"
            ),
            default="general",
            key=f"{key_prefix}_kind",
        )
        if kind is None:
            kind = "general"

        case: dict[str, Any]
        section_key: str | None = None

        if kind == "general":
            case = _anchor_case_for_general(eligible)
            st.caption(
                "General training question — not about a specific case part."
            )
        else:
            case_id = st.selectbox(
                "Which case?",
                options=list(case_by_id),
                format_func=lambda value: case_label(case_by_id[value]),
                key=f"{key_prefix}_case",
            )
            case = case_by_id[str(case_id)]

            topics = _case_topic_options()
            topic_keys = [
                key if key is not None else "__general__" for key, _ in topics
            ]
            labels = {
                (key if key is not None else "__general__"): label
                for key, label in topics
            }
            selected = st.selectbox(
                "Topic",
                options=topic_keys,
                format_func=lambda value: labels[value],
                key=f"{key_prefix}_topic",
            )
            section_key = None if selected == "__general__" else selected

        draft_key = f"{key_prefix}_draft"
        draft = comment_box(
            key=draft_key,
            placeholder=(
                "What do you need help with? Paste screenshots with Ctrl+V / Cmd+V"
            ),
            submit_label="Send question",
        )
        if not draft.submitted:
            return

        body = draft.text.strip()
        if not body and not draft.images:
            st.warning("Write a question or paste a screenshot.")
            return

        try:
            question_id = repository.ask_question(
                case_id=str(case["id"]),
                body=body or "See attached screenshot(s).",
                section_key=section_key,
            )
            if draft.images:
                _upload_question_images(
                    repository,
                    user_id=user_id,
                    case_id=str(case["id"]),
                    question_id=question_id,
                    images=list(draft.images),
                )
        except (APIError, ValueError, Exception) as exc:
            message = getattr(exc, "message", None) or str(exc)
            st.error(message)
            return

        clear_comment_draft(draft_key)
        st.toast("Question sent to your trainer")
        st.rerun()


def render_ask_question_entry(
    repository: TrainingRepository,
    *,
    user_id: str,
    case: dict[str, Any],
    key_prefix: str,
    default_scope: str = "general",
) -> None:
    """Ask box on a case page — topic is general-in-case or a review section."""
    del default_scope
    if case.get("status") == "not_started":
        st.caption("Questions unlock after this case is assigned.")
        return

    with st.container(border=True):
        st.markdown("**Ask a question**")
        st.caption(
            f"About {case_label(case)} — pick a topic, then send to your trainer."
        )

        topics = _case_topic_options()
        topic_keys = [
            key if key is not None else "__general__" for key, _ in topics
        ]
        labels = {
            (key if key is not None else "__general__"): label
            for key, label in topics
        }
        selected = st.selectbox(
            "Topic",
            options=topic_keys,
            format_func=lambda value: labels[value],
            key=f"{key_prefix}_topic_{case['id']}",
        )
        section_key = None if selected == "__general__" else selected

        draft_key = f"{key_prefix}_ask_{case['id']}"
        draft = comment_box(
            key=draft_key,
            placeholder=(
                "What do you need help with? Paste screenshots with Ctrl+V / Cmd+V"
            ),
            submit_label="Send question",
        )
        if not draft.submitted:
            return

        body = draft.text.strip()
        if not body and not draft.images:
            st.warning("Write a question or paste a screenshot.")
            return

        try:
            question_id = repository.ask_question(
                case_id=str(case["id"]),
                body=body or "See attached screenshot(s).",
                section_key=section_key,
            )
            if draft.images:
                _upload_question_images(
                    repository,
                    user_id=user_id,
                    case_id=str(case["id"]),
                    question_id=question_id,
                    images=list(draft.images),
                )
        except (APIError, ValueError, Exception) as exc:
            message = getattr(exc, "message", None) or str(exc)
            st.error(message)
            return

        clear_comment_draft(draft_key)
        st.toast("Question sent to your trainer")
        st.rerun()


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

    render_ask_question_entry(
        repository,
        user_id=user_id,
        case=case,
        key_prefix="trainee_q_tab",
        default_scope="general",
    )

    if not questions:
        st.caption("No questions on this case yet.")
        return

    st.markdown("#### Thread")
    for question in questions:
        status = str(question.get("status") or "open")
        unread = is_unread_answer(question)
        title = (
            f"{question_section_label(question.get('section_key'))} · "
            f"{question_status_label(status)}"
        )
        panel = st.expander(
            title,
            expanded=unread or status != "resolved",
            key=f"trainee_question_{question['id']}",
            on_change="rerun",
            icon=":material/mark_email_unread:" if unread else None,
        )
        if not panel.open:
            continue
        with panel:
            if unread:
                try:
                    repository.mark_question_viewed(question["id"])
                except Exception:
                    pass
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
    """Compact list of OPEN questions only; answered/resolved ones live in
    each case's Questions tab."""
    st.subheader("Open questions")
    rows = repository.list_questions_for_trainer(status="open")
    if not rows:
        st.success("No open questions.", icon=":material/check_circle:")
        return

    for row in rows:
        case = row.get("cases") if isinstance(row.get("cases"), dict) else {}
        trainee = case.get("trainees") if isinstance(case.get("trainees"), dict) else {}
        trainee_name = trainee.get("full_name") or "Trainee"
        label = case_catalog_label(case) if case else "?"
        body = str(row.get("body") or "").strip()
        title = body.splitlines()[0][:90] if body else (
            question_section_label(row.get("section_key"))
        )
        with st.container(border=True):
            left, right = st.columns([3, 1], vertical_alignment="center")
            left.markdown(
                f"**{title}**  \n"
                f":gray[{trainee_name} · Case {label}]"
            )
            if right.button(
                "Jump to answer",
                key=f"jump_q_{row['id']}",
                width="stretch",
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
            if status in {"open", "answered"}:
                head_cols = st.columns([2, 1], vertical_alignment="center")
                with head_cols[0]:
                    _status_badge(status)
                with head_cols[1]:
                    if status == "answered" and st.button(
                        "Mark as resolved",
                        key=f"trainer_resolve_q_{question['id']}",
                        type="secondary",
                        width="stretch",
                    ):
                        try:
                            repository.set_question_status(
                                question["id"], "resolved"
                            )
                        except APIError as exc:
                            st.error(exc.message)
                        else:
                            st.toast("Resolved")
                            st.rerun()

                st.write(question.get("body") or "")
                _render_question_screenshots(
                    repository,
                    question.get("question_screenshots") or [],
                    key_prefix=f"trq_{question['id']}",
                )

                if question.get("answer_body"):
                    st.markdown("**Your answer**")
                    st.write(question["answer_body"])

                answer_key = f"answer_body_{question['id']}"
                st.session_state.setdefault(
                    answer_key,
                    question.get("answer_body") or "",
                )
                with st.form(
                    f"answer_form_{question['id']}",
                    border=False,
                ):
                    answer = st.text_area(
                        "Answer",
                        key=answer_key,
                        height=120,
                        placeholder="Write the complete answer here…",
                    )
                    send_answer = st.form_submit_button(
                        "Send answer",
                        type="primary",
                        width="content",
                        icon=":material/send:",
                    )
                if send_answer:
                    try:
                        repository.answer_question(question["id"], answer)
                    except APIError as exc:
                        st.error(exc.message)
                    else:
                        st.toast("Answer sent")
                        st.rerun()
            elif status == "resolved":
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
                if st.button(
                    "Reopen",
                    key=f"trainer_reopen_q_{question['id']}",
                    type="secondary",
                ):
                    try:
                        repository.set_question_status(question["id"], "open")
                    except APIError as exc:
                        st.error(exc.message)
                    else:
                        st.toast("Reopened")
                        st.rerun()


def render_trainee_question_inbox(
    repository: TrainingRepository,
    *,
    user_id: str,
    trainee: dict[str, Any],
    cases: list[dict[str, Any]],
) -> None:
    """Global, filterable inbox across every case — not just one at a time."""
    st.subheader("Questions")
    rows = repository.list_questions_for_trainee(trainee["id"])
    unread = count_unread_answers(rows)

    metrics = st.columns(3)
    metrics[0].metric("Unread answers", unread)
    metrics[1].metric("Open", count_open_questions(rows))
    metrics[2].metric("Total", len(rows))

    # Always visible — not buried in an expander.
    render_home_ask_question(
        repository,
        user_id=user_id,
        cases=cases,
        key_prefix="question_inbox_ask",
    )

    if not rows:
        st.caption("No questions yet — ask one above.")
        return

    case_labels = {
        str(row["id"]): case_label(row) for row in cases
    }
    filters = st.columns([1.4, 1])
    with filters[0]:
        case_filter = st.selectbox(
            "Case",
            options=["__all__", *case_labels],
            format_func=(
                lambda value: "All cases"
                if value == "__all__"
                else case_labels.get(value, value)
            ),
            key="question_inbox_case_filter",
        )
    with filters[1]:
        status_filter = st.segmented_control(
            "Status",
            options=STATUS_FILTER_OPTIONS,
            format_func=lambda value: (
                "All" if value == "all" else question_status_label(value)
            ),
            default="all",
            key="question_inbox_status_filter",
        )
    if status_filter is None:
        status_filter = "all"

    filtered = [
        row
        for row in rows
        if (case_filter == "__all__" or str(row.get("case_id")) == case_filter)
        and (status_filter == "all" or row.get("status") == status_filter)
    ]
    if not filtered:
        st.caption("No questions match these filters.")
        return

    st.markdown("#### Thread")
    for question in filtered:
        case = question.get("cases") if isinstance(question.get("cases"), dict) else {}
        status = str(question.get("status") or "open")
        unread_flag = is_unread_answer(question)
        case_bit = case_label(case) if case else "Case"
        title = (
            f"{case_bit} · {question_section_label(question.get('section_key'))} · "
            f"{question_status_label(status)}"
        )
        if unread_flag:
            icon = ":material/mark_email_unread:"
        elif status == "resolved":
            icon = ":material/check_circle:"
        elif status == "answered":
            icon = ":material/mark_chat_read:"
        else:
            icon = ":material/help:"

        panel = st.expander(
            title,
            expanded=unread_flag,
            key=f"inbox_question_{question['id']}",
            on_change="rerun",
            icon=icon,
        )
        if not panel.open:
            continue
        with panel:
            if unread_flag:
                try:
                    repository.mark_question_viewed(question["id"])
                except Exception:
                    pass
            _status_badge(status)
            st.write(question.get("body") or "")
            _render_question_screenshots(
                repository,
                question.get("question_screenshots") or [],
                key_prefix=f"inbox_q_{question['id']}",
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
                    key=f"inbox_resolve_{question['id']}",
                    width="stretch",
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
                    key=f"inbox_reopen_{question['id']}",
                    width="stretch",
                ):
                    try:
                        repository.set_question_status(question["id"], "open")
                    except APIError as exc:
                        st.error(exc.message)
                    else:
                        st.toast("Question reopened")
                        st.rerun()
            if actions[1].button(
                "Open case",
                key=f"inbox_open_case_{question['id']}",
                width="stretch",
                icon=":material/open_in_new:",
            ):
                st.switch_page(
                    "app_pages/trainee_case_workspace.py",
                    query_params={"case": question.get("case_id")},
                )
