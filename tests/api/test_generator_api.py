from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from src.api.generator_api import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_create_generator_job_proxies_signed_request():
    with patch("src.api.generator_api.requests.post") as mock_post:
        upstream = MagicMock()
        upstream.status_code = 200
        upstream.json.return_value = {"job_id": "job-123", "status": "queued"}
        mock_post.return_value = upstream

        resp = client.post(
            "/api/generator/jobs",
            json={
                "curriculum_id": "ng-bio-ss1",
                "topic_title": "Cell Division",
                "topic_description": "Describe mitosis",
                "content_format": "Teacher Guide",
                "target_level": "Proficient",
                "requested_by": "admin",
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == "job-123"
        assert data["status"] == "queued"

        _, kwargs = mock_post.call_args
        assert kwargs["headers"]["X-Hub-Signature"]
        assert kwargs["headers"]["X-Hub-Timestamp"]


def test_get_generator_job_proxies_signed_request():
    with patch("src.api.generator_api.requests.get") as mock_get:
        upstream = MagicMock()
        upstream.status_code = 200
        upstream.json.return_value = {"job_id": "job-123", "status": "succeeded", "content_markdown": "# done"}
        mock_get.return_value = upstream

        resp = client.get("/api/generator/jobs/job-123")

        assert resp.status_code == 200
        assert resp.json()["status"] == "succeeded"
        _, kwargs = mock_get.call_args
        assert kwargs["headers"]["X-Hub-Signature"]
