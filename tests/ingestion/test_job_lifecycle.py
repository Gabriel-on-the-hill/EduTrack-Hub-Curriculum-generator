from src.ingestion.schemas import ExtractedCompetency, StandardizedCompetency, CompetencyMetadata
from src.ingestion.worker import ingest_sync


def test_job_lifecycle_success(monkeypatch):
    statuses: list[str] = []

    monkeypatch.setattr("src.ingestion.worker.init_db", lambda: None)
    monkeypatch.setattr("src.ingestion.worker.create_ingestion_job", lambda **kwargs: kwargs["job_id"])
    monkeypatch.setattr(
        "src.ingestion.worker.mark_job_status",
        lambda job_id, source_url, requested_by, status, reason=None: statuses.append(status),
    )
    monkeypatch.setattr("src.ingestion.worker.download_file", lambda url: "/tmp/curriculum.pdf")
    monkeypatch.setattr("src.ingestion.worker.compute_checksum", lambda path: "abc123def456")
    monkeypatch.setattr("src.ingestion.worker.store_snapshot", lambda path: path)
    monkeypatch.setattr("src.ingestion.worker.parse_pdf", lambda path: "curriculum text")
    monkeypatch.setattr("src.ingestion.worker.validate_document", lambda url, text: {"status": "approved"})
    monkeypatch.setattr(
        "src.ingestion.worker.heuristic_extract",
        lambda text: [
            ExtractedCompetency(
                title="Cell Division",
                description="Describe mitosis",
                learning_outcomes=["Describe mitosis"],
                source_chunk_id="chunk-1",
            )
        ],
    )
    monkeypatch.setattr("src.ingestion.worker.store_curriculum_and_chunks", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "src.ingestion.worker.standardize_batch",
        lambda raw_items, llm_provider=None: [
            StandardizedCompetency(
                standardized_id="std-1",
                original_text="Cell Division - Describe mitosis",
                standardized_text="Explain mitosis",
                action_verb="explain",
                content="mitosis",
                context=None,
                bloom_level="understand",
                complexity_level="medium",
                source_chunk_id="chunk-1",
                extraction_confidence=0.95,
                llm_provenance={},
            )
        ],
    )
    monkeypatch.setattr("src.ingestion.services.store_standardized_competencies", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "src.ingestion.worker.predict_metadata",
        lambda items, llm_provider=None: {
                "std-1": CompetencyMetadata(
                    standardized_id="std-1",
                    subject="Biology",
                    grade_level="Grade 9",
                    domain="Cell Biology",
                confidence_score=0.9,
                tags=["mitosis"],
                llm_provenance={},
            )
        },
    )
    monkeypatch.setattr("src.ingestion.services.store_competency_metadata", lambda *args, **kwargs: None)
    monkeypatch.setattr("src.ingestion.worker.enqueue_embedding_job", lambda curriculum_id: None)
    monkeypatch.setattr("src.ingestion.worker.update_ingestion_job", lambda *args, **kwargs: None)

    result = ingest_sync("https://example.com/curriculum.pdf", requested_by="qa", job_id="job-success")

    assert result["status"] == "success"
    assert statuses == ["running", "success"]


def test_job_lifecycle_manual_review(monkeypatch):
    statuses: list[tuple[str, str | None]] = []

    monkeypatch.setattr("src.ingestion.worker.init_db", lambda: None)
    monkeypatch.setattr("src.ingestion.worker.create_ingestion_job", lambda **kwargs: kwargs["job_id"])
    monkeypatch.setattr(
        "src.ingestion.worker.mark_job_status",
        lambda job_id, source_url, requested_by, status, reason=None: statuses.append((status, reason)),
    )
    monkeypatch.setattr("src.ingestion.worker.download_file", lambda url: "/tmp/curriculum.pdf")
    monkeypatch.setattr("src.ingestion.worker.compute_checksum", lambda path: "abc123def456")
    monkeypatch.setattr("src.ingestion.worker.store_snapshot", lambda path: path)
    monkeypatch.setattr("src.ingestion.worker.parse_pdf", lambda path: "restricted content")
    monkeypatch.setattr(
        "src.ingestion.worker.validate_document",
        lambda url, text: {"status": "rejected", "reason": "restricted"},
    )
    monkeypatch.setattr("src.ingestion.worker.update_ingestion_job", lambda *args, **kwargs: None)

    result = ingest_sync("https://example.com/curriculum.pdf", requested_by="qa", job_id="job-review")

    assert result == {"status": "pending_manual_review", "reason": "restricted", "job_id": "job-review"}
    assert statuses == [("running", None), ("pending_manual_review", "restricted")]


def test_job_lifecycle_failure(monkeypatch):
    statuses: list[tuple[str, str | None]] = []

    monkeypatch.setattr("src.ingestion.worker.init_db", lambda: None)
    monkeypatch.setattr("src.ingestion.worker.create_ingestion_job", lambda **kwargs: kwargs["job_id"])
    monkeypatch.setattr(
        "src.ingestion.worker.mark_job_status",
        lambda job_id, source_url, requested_by, status, reason=None: statuses.append((status, reason)),
    )
    monkeypatch.setattr("src.ingestion.worker.download_file", lambda url: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr("src.ingestion.worker.update_ingestion_job", lambda *args, **kwargs: None)

    result = ingest_sync("https://example.com/curriculum.pdf", requested_by="qa", job_id="job-failed")

    assert result == {"status": "failed", "reason": "boom", "job_id": "job-failed"}
    assert statuses == [("running", None), ("failed", "boom")]
