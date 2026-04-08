from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.ingestion.api import router


def test_hub_submit_poll_save(monkeypatch):
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    jobs = {
        "hub-job-1": {
            "job_id": "hub-job-1",
            "source_url": "https://example.com/curriculum.pdf",
            "status": "success",
            "requested_by": "staging",
            "decision_reason": None,
            "result_payload": {"status": "success", "curriculum_id": "curr-123"},
            "created_at": "2026-03-20T00:00:00",
            "updated_at": "2026-03-20T00:00:00",
        }
    }

    monkeypatch.setattr(
        "src.ingestion.api.ingest_sync",
        lambda url, requested_by="system": {
            "status": "success",
            "job_id": "hub-job-1",
            "curriculum_id": "curr-123",
        },
    )
    monkeypatch.setattr("src.ingestion.api.get_ingestion_job", lambda job_id: jobs.get(job_id))
    monkeypatch.setattr(
        "src.ingestion.api.update_ingestion_job",
        lambda job_id, **kwargs: jobs[job_id].update({"status": kwargs["status"], "result_payload": kwargs.get("result_payload")}),
    )

    submit = client.post(
        "/hub/jobs",
        json={"url": "https://example.com/curriculum.pdf", "requested_by": "staging"},
    )
    assert submit.status_code == 200
    assert submit.json()["job_id"] == "hub-job-1"

    poll = client.get("/hub/jobs/hub-job-1")
    assert poll.status_code == 200
    assert poll.json()["status"] == "success"

    save = client.post("/hub/jobs/hub-job-1/save")
    assert save.status_code == 200
    assert save.json()["status"] == "saved"
    assert jobs["hub-job-1"]["status"] == "saved"
