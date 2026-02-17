# src/ingestion/worker.py
import logging
from datetime import datetime
from uuid import uuid4
from typing import Dict, Any, Optional

from .parser import download_file, parse_pdf, parse_html, compute_checksum
from .gatekeeper import validate_document
from .extractor import heuristic_extract
from .standardizer import standardize_batch
from .tagger import predict_metadata
from .services import (
    store_snapshot, persist_job_pending, store_curriculum_and_chunks,
    init_db
)
from .schemas import ExtractorOutput

logger = logging.getLogger(__name__)

# Mock for status marking since we don't have the job table wired fully in prev steps
def mark_job_status(job_id, source_url, requested_by, status, reason=None):
    logger.info(f"JOB STATUS: {job_id} -> {status} ({reason})")

def enqueue_embedding_job(curriculum_id):
    logger.info(f"Enqueuing embedding for {curriculum_id}")

def ingest_sync(url: str, requested_by: str = "system", job_id: str | None = None, provider_config: dict | None = None) -> Dict[str, Any]:
    """Orchestrate ingestion end-to-end, including standardization & tagging."""
    job_id = job_id or f"ingest-{uuid4().hex}"
    logger.info("Starting ingest job %s for %s", job_id, url)
    
    init_db()

    # Persist job entry
    try:
        mark_job_status(job_id, url, requested_by, status="running")
    except Exception:
        logger.exception("Failed to mark job status; continuing...")

    try:
        # 1. Download snapshot
        local_path = download_file(url)
        checksum = compute_checksum(local_path)
        snapshot_path = store_snapshot(local_path) # Adapted signature

        # 2. Parse into chunks
        if local_path.lower().endswith(".pdf"):
            # parse_pdf returns string in phase 2 impl, need to adapt if it returned chunks
            # Checking phase 2 parser.py... it returned text. 
            # Phase 2 extractor takes text. 
            # Phase 3 prompt implies it maps chunks.
            # Let's check if we need to mock chunking or if parser/extractor does it.
            # For now, using existing flow: text -> heuristic_extract -> ExtractorOutput (list of competencies)
            text = parse_pdf(local_path)
        else:
            text = parse_html(local_path)

        decision = validate_document(url, text) # returns dict in Phase 2

        if decision["status"] == "rejected":
             # Adapt decision to object if needed, using dict for now as per Phase 2
            mark_job_status(job_id, url, requested_by, status="pending_manual_review", reason=decision.get("reason"))
            return {"status": "pending_manual_review", "reason": decision.get("reason")}

        # 3. Extract structured competencies (Architect)
        # Using Phase 2 heuristic_extract which returns List[ExtractedCompetency]
        competencies = heuristic_extract(text)
        
        # 4. Persist curriculum and chunks (idempotent)
        # store_curriculum_and_chunks in Phase 2 logic persists chunks from competencies list
        store_curriculum_and_chunks(competencies)
        
        # We need an ID for phase 3 linkage. Phase 2 implementation didn't return one explicitly.
        # We'll generate one or use a deterministic one based on checksum/url.
        curriculum_id = f"curr-{checksum[:12]}" 

        # 5. Standardize using LLM
        # Prepare raw_items for standardizer: map each competency description to source_chunk_id
        raw_items = []
        for comp in competencies:
            # Phase 2 model: ExtractedCompetency has title, description, source_chunk_id
            raw_items.append({"text": comp.title + ((" - " + (comp.description or "")) if comp.description else ""), "source_chunk_id": comp.source_chunk_id})

        # Use provider config (e.g., {"provider":"openai", "api_key":"..."})
        sd_llm = None
        if provider_config:
            # We would init a provider instance here or pass config
            pass

        standardized_list = standardize_batch(raw_items, llm_provider=None)  # will use default provider from llm_client if None

        # Persist standardized competencies
        from .services import store_standardized_competencies
        store_standardized_competencies(curriculum_id, standardized_list)

        # 6. Tagging / metadata
        metadata_map = predict_metadata(standardized_list, llm_provider=None)
        from .services import store_competency_metadata
        store_competency_metadata(metadata_map)

        # 7. Enqueue embeddings & finish
        enqueue_embedding_job(curriculum_id)

        mark_job_status(job_id, url, requested_by, status="success")
        return {
            "status": "success", 
            "curriculum_id": curriculum_id,
            "competencies": len(competencies),
            "standardized": len(standardized_list)
        }
    except Exception as e:
        logger.exception("Ingest job failed: %s", e)
        mark_job_status(job_id, url, requested_by, status="failed", reason=str(e))
        return {"status": "failed", "reason": str(e)}

def enqueue_ingest_job(url: str, requested_by: str):
    """
    Enqueue an ingestion job. 
    In a real production setup, this would push to Redis/SQS.
    For this demo, we'll log it. 
    If you want immediate execution in dev, you could call ingest_sync here.
    """
    logger.info(f"ENQUEUEING JOB: {url} requested by {requested_by}")
    # For demo purposes, we can try to run it immediately or just leave it logged.
    # ingest_sync(url, requested_by) 

