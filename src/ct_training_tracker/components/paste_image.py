"""Jira-style comment box: type text and paste screenshots into the same field."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

import streamlit as st

_HTML = """
<div class="comment-box">
  <textarea
    id="editor"
    rows="4"
    placeholder="Write a comment… Paste screenshots here with Ctrl+V / Cmd+V"
  ></textarea>
  <div id="previews" class="previews"></div>
  <div id="status" class="status"></div>
</div>
"""

_CSS = """
.comment-box {
  border: 1px solid var(--st-border-color, #e2e8f0);
  border-radius: 0.65rem;
  background: var(--st-secondary-background-color, #ffffff);
  padding: 0.7rem 0.8rem 0.75rem;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.comment-box:focus-within {
  border-color: var(--st-primary-color, #0f766e);
  box-shadow: 0 0 0 3px color-mix(
    in srgb,
    var(--st-primary-color, #0f766e) 22%,
    transparent
  );
}
#editor {
  width: 100%;
  min-height: 5.5rem;
  resize: vertical;
  border: none;
  outline: none;
  background: transparent;
  color: var(--st-text-color, #0f172a);
  font: inherit;
  line-height: 1.45;
}
#editor:focus {
  outline: none;
}
.previews {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.45rem;
}
.preview {
  position: relative;
  width: 104px;
  height: 78px;
  border-radius: 0.45rem;
  overflow: hidden;
  border: 1px solid var(--st-border-color, #e2e8f0);
  background: var(--st-background-color, #f8fafc);
}
.preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.preview button {
  position: absolute;
  top: 4px;
  right: 4px;
  border: none;
  border-radius: 999px;
  width: 20px;
  height: 20px;
  line-height: 20px;
  font-size: 13px;
  cursor: pointer;
  background: rgba(15, 23, 42, 0.72);
  color: #fff;
  padding: 0;
}
.status {
  margin-top: 0.4rem;
  font-size: 0.82rem;
  color: var(--st-text-color, #0f172a);
  opacity: 0.72;
  min-height: 1.1em;
}
"""

_JS = """
export default function (component) {
  const { parentElement, setStateValue, data } = component
  const editor = parentElement.querySelector("#editor")
  const previews = parentElement.querySelector("#previews")
  const status = parentElement.querySelector("#status")
  if (!editor || !previews || !status) return

  const placeholder =
    (data && data.placeholder) ||
    "Write a comment… Paste screenshots here with Ctrl+V / Cmd+V"
  editor.placeholder = placeholder

  const nextText = (data && data.text) ?? ""
  if (editor.value !== nextText) editor.value = nextText

  let images = Array.isArray(data && data.images) ? [...data.images] : []
  let textTimer = null

  const setStatus = (text) => {
    status.textContent = text || ""
  }

  const emit = () => {
    setStateValue("text", editor.value)
    setStateValue("images", images)
  }

  const renderPreviews = () => {
    previews.innerHTML = ""
    images.forEach((image, index) => {
      const wrap = document.createElement("div")
      wrap.className = "preview"
      const img = document.createElement("img")
      img.src = `data:${image.mime_type};base64,${image.data_base64}`
      img.alt = image.filename || "screenshot"
      const remove = document.createElement("button")
      remove.type = "button"
      remove.textContent = "×"
      remove.title = "Remove"
      remove.onclick = (event) => {
        event.preventDefault()
        event.stopPropagation()
        images = images.filter((_, i) => i !== index)
        renderPreviews()
        emit()
        setStatus(images.length ? `${images.length} screenshot(s)` : "")
      }
      wrap.appendChild(img)
      wrap.appendChild(remove)
      previews.appendChild(wrap)
    })
  }

  const addImageFile = (file) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = String(reader.result || "")
      const comma = result.indexOf(",")
      const dataBase64 = comma >= 0 ? result.slice(comma + 1) : ""
      if (!dataBase64) {
        setStatus("Could not read pasted image.")
        return
      }
      const mime = file.type || "image/png"
      const ext = mime.includes("jpeg") || mime.includes("jpg")
        ? "jpg"
        : mime.includes("webp")
          ? "webp"
          : mime.includes("gif")
            ? "gif"
            : "png"
      images = [
        ...images,
        {
          mime_type: mime,
          filename: `screenshot_${Date.now()}_${images.length + 1}.${ext}`,
          data_base64: dataBase64,
        },
      ]
      renderPreviews()
      emit()
      setStatus(`Pasted ${images.length} screenshot(s). Keep typing if needed.`)
    }
    reader.onerror = () => setStatus("Could not read pasted image.")
    reader.readAsDataURL(file)
  }

  editor.oninput = () => {
    clearTimeout(textTimer)
    textTimer = setTimeout(() => {
      setStateValue("text", editor.value)
    }, 200)
  }

  editor.onblur = () => {
    clearTimeout(textTimer)
    setStateValue("text", editor.value)
  }

  editor.onpaste = (event) => {
    const items = event.clipboardData && event.clipboardData.items
    if (!items) return
    let handledImage = false
    for (const item of items) {
      if (!item.type || !item.type.startsWith("image/")) continue
      const file = item.getAsFile()
      if (!file) continue
      handledImage = true
      addImageFile(file)
    }
    if (handledImage) {
      clearTimeout(textTimer)
      setStateValue("text", editor.value)
      const hasText = Array.from(items).some(
        (item) => item.type === "text/plain"
      )
      if (!hasText) event.preventDefault()
    }
  }

  renderPreviews()
  if (images.length) {
    setStatus(`${images.length} screenshot(s) attached`)
  }

  return () => {
    clearTimeout(textTimer)
    editor.oninput = null
    editor.onblur = null
    editor.onpaste = null
  }
}
"""

_COMMENT_BOX = st.components.v2.component(
    "ct_jira_comment_box",
    html=_HTML,
    css=_CSS,
    js=_JS,
)


@dataclass(frozen=True, slots=True)
class PastedImage:
    filename: str
    mime_type: str
    content: bytes


@dataclass(frozen=True, slots=True)
class CommentDraft:
    text: str
    images: list[PastedImage]


def decode_image_payload(payload: dict[str, Any] | None) -> PastedImage | None:
    if not isinstance(payload, dict):
        return None
    data_b64 = payload.get("data_base64")
    if not data_b64:
        return None
    try:
        content = base64.b64decode(data_b64)
    except Exception:
        return None
    return PastedImage(
        filename=str(payload.get("filename") or "screenshot.png"),
        mime_type=str(payload.get("mime_type") or "image/png"),
        content=content,
    )


def decode_pasted_payload(payload: dict[str, Any] | str | None) -> PastedImage | None:
    """Backward-compatible single-image decoder used by tests/helpers."""
    if isinstance(payload, dict) and "data_base64" in payload:
        return decode_image_payload(payload)
    return None


def comment_box(
    *,
    key: str,
    placeholder: str | None = None,
    reset_token: str = "",
) -> CommentDraft:
    """Jira-like comment field: type text and paste screenshots in-place."""
    state_key = f"{key}__draft"
    if reset_token:
        seen_key = f"{key}__reset"
        if st.session_state.get(seen_key) != reset_token:
            st.session_state[seen_key] = reset_token
            st.session_state.pop(state_key, None)

    existing = st.session_state.get(state_key) or {}
    text = str(existing.get("text") or "")
    raw_images = list(existing.get("images") or [])

    result = _COMMENT_BOX(
        data={
            "placeholder": placeholder
            or "Write a comment… Paste screenshots here with Ctrl+V / Cmd+V",
            "text": text,
            "images": raw_images,
        },
        key=key,
        on_text_change=lambda: None,
        on_images_change=lambda: None,
        height=190,
    )

    next_text = str(getattr(result, "text", None) or text)
    next_images = getattr(result, "images", None)
    if next_images is None:
        next_images = raw_images
    if not isinstance(next_images, list):
        next_images = raw_images

    st.session_state[state_key] = {"text": next_text, "images": next_images}

    decoded: list[PastedImage] = []
    for item in next_images:
        image = decode_image_payload(item if isinstance(item, dict) else None)
        if image is not None:
            decoded.append(image)

    return CommentDraft(text=next_text, images=decoded)


def clear_comment_draft(key: str) -> None:
    st.session_state.pop(f"{key}__draft", None)
