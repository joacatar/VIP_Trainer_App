from ct_training_tracker.auth import clear_session


def test_clear_session_removes_authentication_only() -> None:
    session = {
        "access_token": "access",
        "refresh_token": "refresh",
        "user_id": "user",
        "selected_case": "case",
    }

    clear_session(session)

    assert session == {"selected_case": "case"}
