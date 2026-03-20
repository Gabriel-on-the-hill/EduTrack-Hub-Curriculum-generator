from app_additions.resource_generation_ui import (
    build_generation_payload,
    is_success_job_state,
    is_terminal_job_state,
    map_output_label_to_request_type,
    normalize_job_state,
)


def test_output_labels_map_deterministically() -> None:
    assert map_output_label_to_request_type("Teacher Guide") == "lesson_plan"
    assert map_output_label_to_request_type("Worksheet") == "summary"
    assert map_output_label_to_request_type("Exam Paper") == "quiz"


def test_output_label_mapping_rejects_unknown_labels() -> None:
    try:
        map_output_label_to_request_type("Poster")
    except ValueError as exc:
        assert "Unsupported output label" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unsupported label")


def test_build_generation_payload_cleans_empty_constraints() -> None:
    payload = build_generation_payload(
        curriculum_id="ng-bio-ss1",
        competency_ids=["c1", "c2"],
        output_label="Teacher Guide",
        constraints={
            "duration": "45 minutes",
            "difficulty_level": "Proficient",
            "language": "English",
            "offline_friendly": False,
            "notes": "",
        },
    )

    assert payload == {
        "curriculum_id": "ng-bio-ss1",
        "request_type": "lesson_plan",
        "competency_ids": ["c1", "c2"],
        "constraints": {
            "duration": "45 minutes",
            "difficulty_level": "Proficient",
            "language": "English",
            "offline_friendly": False,
        },
    }


def test_job_state_helpers_cover_terminal_and_success_states() -> None:
    assert normalize_job_state("In Progress") == "in_progress"
    assert is_terminal_job_state("Succeeded") is True
    assert is_terminal_job_state("failed") is True
    assert is_terminal_job_state("running") is False
    assert is_success_job_state("completed") is True
    assert is_success_job_state("error") is False
