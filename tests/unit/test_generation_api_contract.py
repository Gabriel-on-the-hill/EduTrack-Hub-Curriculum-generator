from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.generation_api import router
from src.app_additions.generation_mapping import HubMappingError, map_ui_request_type


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_generate_accepts_valid_backend_request_type() -> None:
    client = _client()
    response = client.post(
        "/v1/generate",
        json={
            "curriculum_id": "987e6543-e21b-12d3-a456-426614174000",
            "request_type": "lesson_plan",
            "constraints": {"offline_friendly": True},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["request"]["request_type"] == "lesson_plan"


def test_generate_rejects_unsupported_request_type_with_structured_422() -> None:
    client = _client()
    response = client.post(
        "/v1/generate",
        json={
            "curriculum_id": "987e6543-e21b-12d3-a456-426614174000",
            "request_type": "Teacher Guide",
            "constraints": {},
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["detail"]["error"] == "validation_error"
    first_issue = body["detail"]["issues"][0]
    assert first_issue["field"] == "request_type"
    assert first_issue["allowed_values"] == ["lesson_plan", "quiz", "summary"]


def test_hub_mapping_translates_ui_label_to_backend_enum() -> None:
    assert map_ui_request_type("Teacher Guide").value == "lesson_plan"


def test_hub_mapping_rejects_unsupported_label() -> None:
    try:
        map_ui_request_type("Flash Cards")
        raise AssertionError("Expected HubMappingError")
    except HubMappingError as exc:
        detail = exc.to_422_detail()
        assert detail["error"] == "validation_error"
        assert detail["issues"][0]["field"] == "request_type"
