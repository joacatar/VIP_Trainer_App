from ct_training_tracker.views.revisions import _collect_file_draft_decisions


def test_collect_file_draft_decisions_reads_checked_slots(monkeypatch) -> None:
    state = {
        "draft_replace_case-1_req-a": True,
        "draft_replace_note_case-1_req-a": "Wrong landmark",
        "draft_replace_case-1_req-b": False,
    }
    monkeypatch.setattr(
        "ct_training_tracker.views.revisions.st.session_state",
        state,
        raising=False,
    )
    # session_state.get is used — wrap a simple mapping
    class _State(dict):
        def get(self, key, default=None):  # noqa: ANN001
            return super().get(key, default)

    monkeypatch.setattr(
        "ct_training_tracker.views.revisions.st.session_state",
        _State(state),
    )

    requirements = [
        {"id": "req-a", "status": "under_review", "kind": "pdf_primary"},
        {"id": "req-b", "status": "under_review", "kind": "pdf_secondary"},
        {"id": "req-c", "status": "accepted", "kind": "ov"},
    ]
    decisions = _collect_file_draft_decisions(requirements, case_id="case-1")
    assert decisions == [
        {
            "requirement_id": "req-a",
            "decision": "rejected",
            "note": "Wrong landmark",
        }
    ]
