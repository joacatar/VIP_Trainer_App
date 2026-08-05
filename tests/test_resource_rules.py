from ct_training_tracker.resource_rules import (
    build_system_resources,
    suggest_resources_for_case,
)


def test_all_cases_get_the_checklist_note() -> None:
    case = {"id": "c1", "set_no": 2, "case_no": 9}

    suggestions = suggest_resources_for_case(case)

    assert any(
        item["resource_type"] == "note" and item["title"] == "Before you submit"
        for item in suggestions
    )


def test_early_set_one_cases_get_the_getting_started_link() -> None:
    early = suggest_resources_for_case({"id": "c1", "set_no": 1, "case_no": 2})
    late = suggest_resources_for_case({"id": "c2", "set_no": 1, "case_no": 5})
    set_two = suggest_resources_for_case({"id": "c3", "set_no": 2, "case_no": 2})

    def has_link(items: list[dict]) -> bool:
        return any(item["resource_type"] == "link" for item in items)

    assert has_link(early)
    assert not has_link(late)
    assert not has_link(set_two)


def test_manual_cases_get_the_manual_note_in_both_sets() -> None:
    for set_no in (1, 2):
        suggestions = suggest_resources_for_case(
            {"id": "c1", "set_no": set_no, "case_no": 12}
        )
        assert any(
            item["title"] == "Manual planning reminder" for item in suggestions
        )


def test_build_system_resources_marks_rows_as_system() -> None:
    cases = [
        {"id": "c1", "set_no": 1, "case_no": 1},
        {"id": "c2", "set_no": 2, "case_no": 16},
    ]

    rows = build_system_resources(cases)

    assert rows
    assert all(row["created_by"] == "system" for row in rows)
    assert all(row["case_id"] in {"c1", "c2"} for row in rows)
    # c1 matches the checklist note + getting started link.
    assert sum(1 for row in rows if row["case_id"] == "c1") == 2
    # c2 only matches the checklist note.
    assert sum(1 for row in rows if row["case_id"] == "c2") == 1


def test_rules_module_is_pure() -> None:
    import ct_training_tracker.resource_rules as module

    source = open(module.__file__).read()
    assert "streamlit" not in source
    assert "supabase" not in source
