import datetime as dt
from typing import Any, cast

from ct_training_tracker.files import storage_object_path, validate_upload
from ct_training_tracker.models import HomeworkAssignment, Profile, Trainee
from supabase import Client

CASE_FILES_BUCKET = "case-files"


class TrainingRepository:
    """Supabase data access for the training tracker."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def get_profile(self, user_id: str) -> Profile | None:
        result = (
            self._client.table("profiles")
            .select("id, role, full_name")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        return cast(Profile | None, result.data if result is not None else None)

    def list_progress(self) -> list[dict[str, Any]]:
        result = (
            self._client.table("trainee_progress")
            .select(
                "trainee_id, full_name, current_phase, total_cases, approved_cases, "
                "overdue_cases, waiting_on_trainer, waiting_on_trainee, "
                "total_files, accepted_files, estimated_completion_date"
            )
            .execute()
        )
        return cast(list[dict[str, Any]], result.data or [])

    def list_active_trainees(self) -> list[Trainee]:
        result = (
            self._client.table("trainees")
            .select("id, full_name, start_date, current_phase")
            .eq("active", True)
            .order("full_name")
            .execute()
        )
        return cast(list[Trainee], result.data or [])

    def get_trainee_for_user(self, user_id: str) -> Trainee | None:
        result = (
            self._client.table("trainees")
            .select("id, full_name, current_phase, start_date")
            .eq("auth_user_id", user_id)
            .maybe_single()
            .execute()
        )
        return cast(Trainee | None, result.data if result is not None else None)

    def list_cases(
        self,
        trainee_id: str,
        *,
        include_files: bool = False,
    ) -> list[dict[str, Any]]:
        columns = (
            "id, set_no, case_no, status, schedule_due_date, due_date, "
            "estimated_completion_date, file_requirements(kind, status)"
            if include_files
            else "id, set_no, case_no, phase, status, schedule_due_date, due_date, "
            "estimated_completion_date"
        )
        result = (
            self._client.table("cases")
            .select(columns)
            .eq("trainee_id", trainee_id)
            .order("set_no")
            .order("case_no")
            .execute()
        )
        return cast(list[dict[str, Any]], result.data or [])

    def create_trainee(
        self,
        *,
        full_name: str,
        email: str | None,
        start_date: dt.date,
        timezone: str,
        created_by: str,
    ) -> None:
        self._client.table("trainees").insert(
            {
                "full_name": full_name,
                "email": email,
                "start_date": start_date.isoformat(),
                "timezone": timezone,
                "created_by": created_by,
            }
        ).execute()

    def assign_homework(
        self,
        *,
        case_id: str,
        title: str,
        instructions: str,
        schedule_due_date: dt.date,
        due_date: dt.date,
    ) -> str:
        result = self._client.rpc(
            "assign_homework",
            {
                "target_case_id": case_id,
                "homework_title": title,
                "homework_instructions": instructions,
                "scheduled_due": schedule_due_date.isoformat(),
                "assigned_due": due_date.isoformat(),
            },
        ).execute()
        return cast(str, result.data)

    def list_homework_for_cases(
        self,
        case_ids: list[str],
    ) -> list[HomeworkAssignment]:
        if not case_ids:
            return []
        result = (
            self._client.table("homework_assignments")
            .select(
                "id, case_id, title, instructions, status, schedule_due_date, "
                "due_date, estimated_due_date, cases(set_no, case_no)"
            )
            .in_("case_id", case_ids)
            .neq("status", "cancelled")
            .order("due_date")
            .execute()
        )
        return cast(list[HomeworkAssignment], result.data or [])

    def list_requirements_for_case(self, case_id: str) -> list[dict[str, Any]]:
        result = (
            self._client.table("file_requirements")
            .select(
                "id, case_id, kind, status, replacement_reason, accepted_at, "
                "case_files(id, version_no, storage_path, original_filename, "
                "mime_type, size_bytes, review_status, review_note, uploaded_at)"
            )
            .eq("case_id", case_id)
            .order("kind")
            .execute()
        )
        rows = cast(list[dict[str, Any]], result.data or [])
        for row in rows:
            versions = sorted(
                row.get("case_files") or [],
                key=lambda item: int(item.get("version_no") or 0),
            )
            row["case_files"] = versions
            row["latest_file"] = versions[-1] if versions else None
        return rows

    def next_file_version(self, requirement_id: str) -> int:
        result = (
            self._client.table("case_files")
            .select("version_no")
            .eq("requirement_id", requirement_id)
            .order("version_no", desc=True)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return 1
        return int(rows[0]["version_no"]) + 1

    def upload_case_file(
        self,
        *,
        user_id: str,
        case_id: str,
        requirement_id: str,
        kind: str,
        filename: str,
        content: bytes,
        mime_type: str | None,
    ) -> str:
        safe_name = validate_upload(kind, filename)
        version_no = self.next_file_version(requirement_id)
        object_path = storage_object_path(
            user_id=user_id,
            case_id=case_id,
            kind=kind,
            version_no=version_no,
            filename=safe_name,
        )
        try:
            self._client.storage.from_(CASE_FILES_BUCKET).upload(
                object_path,
                content,
                file_options={
                    "content-type": mime_type or "application/octet-stream",
                    "upsert": "false",
                },
            )
        except Exception as exc:
            message = str(getattr(exc, "message", None) or exc)
            lowered = message.lower()
            if (
                "maximum allowed size" in lowered
                or "entitytoolarge" in lowered
                or "payload too large" in lowered
            ):
                size_mb = len(content) / (1024 * 1024)
                raise ValueError(
                    f"Supabase Storage rejected this file ({size_mb:.1f} MB). "
                    "Raise Storage → Settings → Global file size limit "
                    "(Free plan max is 50 MB; Pro can go much higher). "
                    "Bucket limit alone is not enough."
                ) from exc
            raise
        try:
            result = self._client.rpc(
                "register_case_file",
                {
                    "target_requirement_id": requirement_id,
                    "file_storage_path": object_path,
                    "file_original_filename": safe_name,
                    "file_mime_type": mime_type,
                    "file_size_bytes": len(content),
                },
            ).execute()
        except Exception:
            self._client.storage.from_(CASE_FILES_BUCKET).remove([object_path])
            raise
        return cast(str, result.data)

    def review_case_file(
        self,
        *,
        file_id: str,
        decision: str,
        note: str = "",
    ) -> None:
        self._client.rpc(
            "review_case_file",
            {
                "target_file_id": file_id,
                "decision": decision,
                "decision_note": note,
            },
        ).execute()

    def create_signed_download_url(
        self,
        storage_path: str,
        *,
        expires_in: int = 300,
    ) -> str:
        result = self._client.storage.from_(CASE_FILES_BUCKET).create_signed_url(
            storage_path,
            expires_in,
        )
        url = (
            result.get("signedURL")
            or result.get("signedUrl")
            or result.get("signed_url")
        )
        if not url:
            raise RuntimeError("Could not create a download link.")
        return cast(str, url)
