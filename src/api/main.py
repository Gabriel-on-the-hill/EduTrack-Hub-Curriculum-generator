"""
EduTrack Generator — Canonical FastAPI Application

Single entrypoint that mounts all existing routers and exposes:
- Workflow A (Pipeline): Async curriculum discovery via LangGraph
- Workflow B (Generate): Sync content generation via ProductionHarness
- Curriculum listing and competency retrieval
- Health check

Run with: uvicorn src.api.main:app --host 0.0.0.0 --port 8000
"""

import asyncio
import logging
import os
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.api.admin_api import router as admin_router
from src.ingestion.api import router as ingestion_router
from src.schemas.base import GenerationRequestType

logger = logging.getLogger(__name__)

# =============================================================================
# APP
# =============================================================================

app = FastAPI(
    title="EduTrack Curriculum Generator",
    version="1.0.0",
    description="Curriculum discovery and content generation service",
)


@app.on_event("startup")
async def on_startup():
    """Run DB migrations on startup so the app works against any DB state."""
    from src.ingestion.services import migrate_db
    try:
        migrate_db()
        logger.info("DB migration completed on startup")
    except Exception as e:
        logger.warning("DB migration skipped (non-SQLite or already up to date): %s", e)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("HUB_ORIGIN", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount existing routers
app.include_router(admin_router)
app.include_router(ingestion_router, prefix="/api/ingestion")


# =============================================================================
# AUTH
# =============================================================================

API_KEY = os.getenv("GENERATOR_API_KEY", "")


async def verify_api_key(x_api_key: str = Header(...)):
    """Validate service-to-service API key."""
    if not API_KEY:
        # No key configured — reject all requests in production
        raise HTTPException(status_code=500, detail="API key not configured")
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


# =============================================================================
# JOB STORE (in-memory; swap for Redis when scaling)
# =============================================================================

jobs: dict[str, dict] = {}


# =============================================================================
# REQUEST / RESPONSE MODELS
# =============================================================================

class PipelineRunRequest(BaseModel):
    """Workflow A input: natural-language curriculum prompt."""
    raw_prompt: str  # e.g. "Grade 9 Biology curriculum for Nigeria"


class GenerateRequest(BaseModel):
    """Workflow B input: generate content from an existing curriculum."""
    curriculum_id: str  # Hub uses cuid, accept as string
    request_type: GenerationRequestType  # lesson_plan | quiz | summary
    competency_ids: list[str] | None = None
    topic_title: str | None = None  # optional override
    topic_description: str | None = None
    duration: str | None = None
    difficulty_level: str | None = None


# =============================================================================
# HEALTH
# =============================================================================

@app.get("/health")
async def health():
    return {"status": "ok", "service": "edutrack-generator"}


# =============================================================================
# WORKFLOW A: PIPELINE (async, job-based)
# =============================================================================

@app.post("/pipeline/run", dependencies=[Depends(verify_api_key)])
async def pipeline_run(request: PipelineRunRequest):
    """
    Start an async curriculum discovery pipeline.

    Returns a job_id immediately; poll /pipeline/status/{job_id} for result.
    """
    job_id = str(uuid4())
    jobs[job_id] = {
        "status": "running",
        "prompt": request.raw_prompt,
        "result": None,
        "error": None,
        "current_node": None,
    }
    asyncio.create_task(_run_pipeline(job_id, request.raw_prompt))
    return {"job_id": job_id, "status": "running"}


async def _run_pipeline(job_id: str, raw_prompt: str):
    """Execute the LangGraph pipeline in background."""
    try:
        from src.orchestrator.graph import compile_curriculum_graph, create_initial_state

        graph = compile_curriculum_graph()
        initial_state = create_initial_state(raw_prompt)

        # LangGraph invoke — runs all nodes sequentially
        final_state = await asyncio.to_thread(graph.invoke, initial_state)

        if final_state.has_error:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"] = final_state.error_message
            jobs[job_id]["error_code"] = getattr(final_state, "error_code", None)
            jobs[job_id]["requires_human_alert"] = final_state.requires_human_alert
        else:
            jobs[job_id]["status"] = "completed"
            jobs[job_id]["result"] = {
                "curriculum_id": str(final_state.curriculum_id) if final_state.curriculum_id else None,
                "country": final_state.normalized_country,
                "country_code": final_state.normalized_country_code,
                "grade": final_state.normalized_grade,
                "subject": final_state.normalized_subject,
                "competency_count": final_state.competency_count,
                "generated_content": final_state.generated_content,
                "coverage": final_state.generation_coverage,
            }
    except Exception as e:
        logger.exception("Pipeline failed for job %s", job_id)
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)


@app.get("/pipeline/status/{job_id}", dependencies=[Depends(verify_api_key)])
async def pipeline_status(job_id: str):
    """Poll pipeline job status."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]


# =============================================================================
# WORKFLOW B: CONTENT GENERATION (synchronous)
# =============================================================================

@app.post("/generate", dependencies=[Depends(verify_api_key)])
async def generate_content(request: GenerateRequest):
    """
    Generate a lesson plan, quiz, or summary from an existing curriculum.

    Uses ProductionHarness with governance, grounding, and shadow execution.
    """
    from sqlalchemy.orm import Session as SASession

    from src.ingestion.services import get_engine
    from src.production.data_access import fetch_curriculum_metadata
    from src.production.harness import ProductionHarness
    from src.production.security import ReadOnlySession
    from src.synthetic.schemas import GroundTruth, SyntheticCurriculumConfig

    try:
        engine = get_engine()
        session = ReadOnlySession(bind=engine)

        # Fetch curriculum metadata to populate config fields
        with SASession(engine) as meta_session:
            metadata = fetch_curriculum_metadata(meta_session, request.curriculum_id)

        if not metadata:
            raise HTTPException(status_code=404, detail="Curriculum not found")

        # Build a proper SyntheticCurriculumConfig with generation fields
        topic = request.topic_title or metadata.get("subject", "Unknown")
        gen_config = SyntheticCurriculumConfig(
            synthetic_id=f"hub-{request.curriculum_id}",
            country=metadata.get("country", "Unknown"),
            country_code=metadata.get("country_code", "XX"),
            jurisdiction=metadata.get("jurisdiction_level", "national"),
            grade=metadata.get("grade", "Unknown"),
            subject=metadata.get("subject", "Unknown"),
            topic_title=topic,
            topic_description=request.topic_description or f"{request.request_type.value} for {topic}",
            content_format=request.request_type.value,
            target_level=request.difficulty_level or "intermediate",
            ground_truth=GroundTruth(
                expected_jurisdiction=metadata.get("jurisdiction_level", "national"),
                expected_grade=metadata.get("grade", "Unknown"),
                expected_subject=metadata.get("subject", "Unknown"),
            ),
        )

        harness = ProductionHarness(
            db_session=session,
            verify_db_level=False,  # Railway may not support pg read-only transactions
        )

        result = await harness.generate_artifact(
            curriculum_id=request.curriculum_id,
            config=gen_config,
            provenance={
                "source": "hub",
                "request_type": request.request_type.value,
                "curriculum_id": request.curriculum_id,
            },
        )

        return {
            "content": result.content_markdown,
            "request_type": request.request_type.value,
            "curriculum_id": request.curriculum_id,
            "metadata": result.metadata,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Generation failed for curriculum %s", request.curriculum_id)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# CURRICULUM LISTING
# =============================================================================

@app.get("/curricula", dependencies=[Depends(verify_api_key)])
async def list_curricula():
    """List all curricula in the Generator's database."""
    from sqlalchemy import text

    from src.ingestion.services import get_engine

    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, country, country_code, grade, subject, status, confidence_score "
                "FROM curricula ORDER BY id DESC"
            )
        ).fetchall()
    return {"curricula": [dict(r._mapping) for r in rows]}


@app.get("/curricula/{curriculum_id}/competencies", dependencies=[Depends(verify_api_key)])
async def get_competencies(curriculum_id: str):
    """List competencies for a specific curriculum."""
    from sqlalchemy.orm import Session as SASession

    from src.ingestion.services import get_engine
    from src.production.data_access import fetch_competencies

    engine = get_engine()
    with SASession(engine) as session:
        try:
            comps = fetch_competencies(session, curriculum_id)
        except Exception as e:
            raise HTTPException(status_code=404, detail=str(e))
    return {"competencies": comps}
