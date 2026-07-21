from ct_training_tracker.config import SupabaseSettings, settings_from_mapping


def test_settings_from_mapping_returns_configuration() -> None:
    settings = settings_from_mapping(
        {
            "SUPABASE_URL": " https://example.supabase.co ",
            "SUPABASE_PUBLISHABLE_KEY": " publishable-key ",
        }
    )

    assert settings == SupabaseSettings(
        url="https://example.supabase.co",
        publishable_key="publishable-key",
    )


def test_settings_from_mapping_requires_both_values() -> None:
    assert settings_from_mapping({}) is None
    incomplete = {"SUPABASE_URL": "https://example.supabase.co"}
    assert settings_from_mapping(incomplete) is None
