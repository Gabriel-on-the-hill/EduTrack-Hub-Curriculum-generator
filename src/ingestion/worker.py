from datetime import datetime
from .parser import download_file, parse_pdf, parse_html, compute_checksum
from .gatekeeper import validate_document
from .extractor import heuristic_extract
from .schemas import IngestionResult
from .services import (
    persist_job_pending,
    store_snapshot,
    store_curriculum_and_chunks,
    init_db,
)


def ingest_sync(url: str) -> IngestionResult:
    init_db()

    path = download_file(url)

    if path.endswith(".pdf"):
        text = parse_pdf(path)
    else:
        text = parse_html(path)

    checksum = compute_checksum(path)
    snapshot_path = store_snapshot(path)

    validation = validate_document(url, text)

    if validation["status"] == "rejected":
        return IngestionResult(
            status="rejected",
            authority_level=None,
            license_tag=None,
            processed_at=datetime.utcnow(),
        )

    competencies = heuristic_extract(text)

    store_curriculum_and_chunks(competencies)

    return IngestionResult(
        status="success",
        authority_level=validation.get("authority_level"),
        license_tag=validation.get("license_tag"),
        competencies=competencies,
        processed_at=datetime.utcnow(),
    )
