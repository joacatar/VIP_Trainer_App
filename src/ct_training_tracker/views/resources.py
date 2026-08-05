"""Per-case resources UI: trainer editor and trainee read-only display."""

from __future__ import annotations

from typing import Any

import streamlit as st
from postgrest.exceptions import APIError

from ct_training_tracker.repository import TrainingRepository

RESOURCE_ICONS = {
    "file": ":material/attach_file:",
    "link": ":material/link:",
    "note": ":material/sticky_note_2:",
}
RESOURCE_TYPES = ("file", "link", "note")


def render_case_resources_editor(
    repository: TrainingRepository,
    *,
    case_id: str,
) -> None:
    """Trainer-side expander: list, edit, delete, and add resources."""
    resources = repository.list_case_resources(case_id)
    with st.expander(
        f"Resources ({len(resources)})",
        icon=":material/library_books:",
    ):
        for row in resources:
            _render_editor_row(repository, row)
        if not resources:
            st.caption("No resources on this case yet.")
        st.markdown("**Add resource**")
        _render_add_form(repository, case_id)


def _render_editor_row(
    repository: TrainingRepository,
    row: dict[str, Any],
) -> None:
    icon = RESOURCE_ICONS.get(str(row.get("resource_type")), ":material/description:")
    with st.container(border=True):
        head = st.columns([3, 1, 1], vertical_alignment="center")
        with head[0]:
            st.markdown(f"{icon} **{row.get('title') or 'Untitled'}**")
            if row.get("created_by") == "system":
                st.caption("suggested")
        with head[1]:
            with st.popover("Edit", width="stretch"):
                _render_edit_form(repository, row)
        with head[2]:
            if st.button(
                "Delete",
                key=f"res_delete_{row['id']}",
                width="stretch",
            ):
                try:
                    repository.delete_case_resource(str(row["id"]))
                except APIError as exc:
                    st.error(exc.message)
                else:
                    st.toast("Resource deleted")
                    st.rerun()
        if row.get("resource_type") == "note":
            if row.get("body"):
                st.markdown(row["body"])
        elif row.get("url"):
            st.markdown(f"[{row['url']}]({row['url']})")


def _render_edit_form(
    repository: TrainingRepository,
    row: dict[str, Any],
) -> None:
    resource_id = str(row["id"])
    title = st.text_input(
        "Title",
        value=str(row.get("title") or ""),
        key=f"res_edit_title_{resource_id}",
    )
    is_note = row.get("resource_type") == "note"
    if is_note:
        body = st.text_area(
            "Note",
            value=str(row.get("body") or ""),
            key=f"res_edit_body_{resource_id}",
        )
        url = None
    else:
        url = st.text_input(
            "URL",
            value=str(row.get("url") or ""),
            key=f"res_edit_url_{resource_id}",
        )
        body = None
    if st.button("Save", key=f"res_edit_save_{resource_id}", type="primary"):
        if not title.strip():
            st.error("Title is required.")
            return
        try:
            repository.update_case_resource(
                resource_id,
                title=title.strip(),
                url=(url or "").strip() or None if not is_note else None,
                body=(body or "").strip() or None if is_note else None,
            )
        except APIError as exc:
            st.error(exc.message)
        else:
            st.toast("Resource updated")
            st.rerun()


def _render_add_form(
    repository: TrainingRepository,
    case_id: str,
) -> None:
    resource_type = st.selectbox(
        "Type",
        options=RESOURCE_TYPES,
        format_func=lambda value: value.title(),
        key=f"res_new_type_{case_id}",
    )
    title = st.text_input("Title", key=f"res_new_title_{case_id}")
    if resource_type == "note":
        body = st.text_area("Note", key=f"res_new_body_{case_id}")
        url = ""
    else:
        url = st.text_input(
            "URL",
            key=f"res_new_url_{case_id}",
            placeholder="Paste a storage/drive link",
        )
        body = ""
    if st.button(
        "Add resource",
        key=f"res_new_add_{case_id}",
        icon=":material/add:",
    ):
        if not title.strip():
            st.error("Title is required.")
            return
        if resource_type == "note" and not body.strip():
            st.error("Note body is required.")
            return
        if resource_type != "note" and not url.strip():
            st.error("URL is required for files and links.")
            return
        try:
            repository.add_case_resource(
                case_id=case_id,
                resource_type=resource_type,
                title=title.strip(),
                url=url.strip() or None,
                body=body.strip() or None,
                created_by="trainer",
            )
        except APIError as exc:
            st.error(exc.message)
        else:
            st.toast("Resource added")
            st.rerun()


def render_case_resources_readonly(
    repository: TrainingRepository,
    *,
    case_id: str,
) -> None:
    """Trainee-side read-only resources; hidden when the case has none."""
    resources = repository.list_case_resources(case_id)
    if not resources:
        return
    with st.container(border=True):
        st.markdown("**Resources**")
        for row in resources:
            icon = RESOURCE_ICONS.get(
                str(row.get("resource_type")), ":material/description:"
            )
            if row.get("resource_type") == "note":
                st.markdown(f"{icon} **{row.get('title') or 'Note'}**")
                if row.get("body"):
                    st.markdown(row["body"])
            elif row.get("url"):
                st.markdown(f"{icon} [{row.get('title') or 'Open'}]({row['url']})")
