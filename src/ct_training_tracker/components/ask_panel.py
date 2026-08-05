"""Floating ask-about-this-case chat panel (Feature 9)."""

from __future__ import annotations

from typing import Any

import streamlit as st
from postgrest.exceptions import APIError

from ct_training_tracker.case_labels import case_label
from ct_training_tracker.questions import question_status_label
from ct_training_tracker.repository import TrainingRepository

_PANEL_OPEN_KEY = "ask_chat_panel_open"


def _inject_ask_panel_styles() -> None:
    st.markdown(
        """
<style>
div.st-key-ask_fab_wrap {
  position: fixed !important;
  bottom: 1.35rem;
  right: 1.35rem;
  z-index: 1000;
  width: auto !important;
}
div.st-key-ask_fab_wrap button {
  width: 3.25rem !important;
  height: 3.25rem !important;
  min-width: 3.25rem !important;
  border-radius: 999px !important;
  padding: 0 !important;
  box-shadow: 0 8px 24px rgba(37, 99, 235, 0.35) !important;
}
div.st-key-ask_fab_wrap button p,
div.st-key-ask_fab_wrap button [data-testid="stMarkdownContainer"] {
  display: none !important;
}
div.st-key-ask_panel_wrap {
  position: fixed !important;
  bottom: 5.1rem;
  right: 1.35rem;
  z-index: 999;
  width: min(380px, calc(100vw - 2rem)) !important;
  max-height: min(520px, calc(100vh - 7rem));
  overflow: auto;
  background: #111827 !important;
  border: 1px solid rgba(148, 163, 184, 0.28) !important;
  border-radius: 0.9rem !important;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.55) !important;
  padding: 0.85rem 0.9rem 0.75rem !important;
}
div.st-key-ask_panel_wrap [data-testid="stChatMessage"] {
  background: transparent !important;
}
div.st-key-ask_panel_wrap [data-testid="stChatMessageContent"] {
  background: #1d4ed8 !important;
  border-radius: 1rem 1rem 0.25rem 1rem !important;
  padding: 0.65rem 0.85rem !important;
  color: #eff6ff !important;
}
div.st-key-ask_panel_wrap [data-testid="stChatMessage"]:has(
  [data-testid="chatAvatarIcon-assistant"]
) [data-testid="stChatMessageContent"],
div.st-key-ask_panel_wrap [data-testid="stChatMessage"]:has(
  [aria-label="Chat message from assistant"]
) [data-testid="stChatMessageContent"] {
  background: #1f2937 !important;
  border-radius: 1rem 1rem 1rem 0.25rem !important;
  color: #e5e7eb !important;
}
div.st-key-ask_status {
  display: flex !important;
  justify-content: center !important;
  margin: 0.35rem 0 0.6rem !important;
}
div.st-key-ask_status p {
  margin: 0 !important;
  padding: 0.35rem 0.75rem !important;
  border-radius: 999px !important;
  background: #1f2937 !important;
  color: #9ca3af !important;
  font-size: 0.75rem !important;
  text-align: center !important;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def _status_caption(question: dict[str, Any], *, trainer_name: str | None) -> str:
    status = str(question.get("status") or "open")
    if status == "open":
        if trainer_name:
            return f"Sent to {trainer_name} · awaiting reply."
        return "Sent to your trainer · awaiting reply."
    if status == "answered":
        return "Answered — mark resolved in Questions when done."
    return question_status_label(status)


@st.fragment
def render_ask_chat_panel(
    repository: TrainingRepository,
    *,
    case: dict[str, Any] | None,
    trainee_id: str | None = None,
) -> None:
    """Fixed FAB + non-modal panel wired to the existing questions model.

    On My cases, pass the next-up case. On Case workspace, pass the open case.
    Hidden when there is no case context.
    """
    if case is None or case.get("status") == "not_started":
        return

    _inject_ask_panel_styles()
    case_id = str(case["id"])
    open_key = f"{_PANEL_OPEN_KEY}_{case_id}"
    if open_key not in st.session_state:
        st.session_state[open_key] = False

    trainer_name: str | None = None
    if trainee_id:
        try:
            trainer_name = repository.get_trainer_display_name_for_trainee(
                trainee_id
            )
        except Exception:
            trainer_name = None

    with st.container(key="ask_fab_wrap", width="content"):
        if st.button(
            "Ask",
            icon=":material/chat:",
            key=f"ask_fab_{case_id}",
            type="primary",
            help="Ask about this case",
            width="content",
        ):
            st.session_state[open_key] = not st.session_state[open_key]

    if not st.session_state[open_key]:
        return

    questions = repository.list_questions_for_case(case_id)
    timeline = list(reversed(questions))

    with st.container(border=True, key="ask_panel_wrap"):
        head_l, head_r = st.columns([5, 1], vertical_alignment="center")
        with head_l:
            st.markdown("**Ask about this case**")
            st.caption(case_label(case))
        with head_r:
            if st.button(
                "✕",
                key=f"ask_panel_close_{case_id}",
                help="Close",
                type="tertiary",
                width="content",
            ):
                st.session_state[open_key] = False
                st.rerun(scope="fragment")

        if not timeline:
            st.caption("No questions on this case yet.")
        else:
            for question in timeline:
                body = str(question.get("body") or "").strip()
                with st.chat_message("user", avatar=":material/person:"):
                    st.write(body or "(screenshot only)")
                with st.container(key=f"ask_status_{question['id']}"):
                    st.markdown(
                        _status_caption(question, trainer_name=trainer_name)
                    )
                answer = str(question.get("answer_body") or "").strip()
                if answer:
                    with st.chat_message(
                        "assistant",
                        avatar=":material/support_agent:",
                    ):
                        st.write(answer)

        prompt = st.chat_input(
            "Ask a question about this case...",
            key=f"ask_panel_input_{case_id}",
        )
        if not prompt or not str(prompt).strip():
            return

        try:
            repository.ask_question(
                case_id=case_id,
                body=str(prompt).strip(),
                section_key=None,
            )
        except (APIError, ValueError, Exception) as exc:
            message = getattr(exc, "message", None) or str(exc)
            st.error(message)
            return

        st.toast("Question sent to your trainer")
        st.rerun(scope="fragment")
