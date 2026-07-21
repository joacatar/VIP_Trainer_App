from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SupabaseSettings:
    url: str
    publishable_key: str


def settings_from_mapping(values: Mapping[str, object]) -> SupabaseSettings | None:
    url = str(values.get("SUPABASE_URL", "")).strip()
    publishable_key = str(values.get("SUPABASE_PUBLISHABLE_KEY", "")).strip()
    if not url or not publishable_key:
        return None
    return SupabaseSettings(url=url, publishable_key=publishable_key)
