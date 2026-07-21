import datetime as dt
from typing import Any, cast

from ct_training_tracker.models import Profile, Trainee
from supabase import Client


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
                "overdue_cases, total_files, accepted_files, estimated_completion_date"
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
            "id, set_no, case_no, status, due_date, estimated_completion_date, "
            "file_requirements(kind, status)"
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
