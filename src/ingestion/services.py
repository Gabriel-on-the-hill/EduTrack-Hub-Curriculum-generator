from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    create_engine,
    JSON,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import shutil
import os
from typing import List, Dict
from .schemas import StandardizedCompetency, CompetencyMetadata

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///demo.db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id = Column(Integer, primary_key=True)
    source_url = Column(String)
    status = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class CurriculumChunk(Base):
    __tablename__ = "curriculum_chunks"

    id = Column(Integer, primary_key=True)
    curriculum_id = Column(Integer)
    content = Column(Text)
    chunk_metadata = Column(JSON)


def init_db():
    Base.metadata.create_all(engine)


def persist_job_pending(url: str):
    session = SessionLocal()
    job = IngestionJob(source_url=url, status="pending")
    session.add(job)
    session.commit()
    session.close()


def store_snapshot(path: str) -> str:
    snapshot_dir = os.getenv("INGEST_SNAPSHOT_DIR", "snapshots")
    os.makedirs(snapshot_dir, exist_ok=True)
    dest = os.path.join(snapshot_dir, os.path.basename(path))
    shutil.copy(path, dest)
    return dest


def store_curriculum_and_chunks(curriculum_id: str, url: str, competencies: List[Any]):
    """
    Persist the curriculum and its competencies to the main tables used by app.py.
    """
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        # 1. Insert Curriculum
        # Check existence
        exists = conn.execute(
            text("SELECT 1 FROM curricula WHERE id = :id"),
            {"id": curriculum_id}
        ).fetchone()

        if not exists:
            # We need to infer country/grade/subject or use placeholders.
            # For now, we'll derive from the URL or use defaults.
            # In a real app, we'd use the ExtractorOutput metadata.
            conn.execute(
                text("""
                    INSERT INTO curricula (id, country, grade, subject, status, source_authority)
                    VALUES (:id, :country, :grade, :subject, 'active', :auth)
                """),
                {
                    "id": curriculum_id,
                    "country": "Imported",
                    "grade": "General",
                    "subject": "General",
                    "auth": url
                }
            )

        # 2. Insert Competencies
        for i, comp in enumerate(competencies):
            # comp is expected to be an object with title, description
            # We assume it has a .title and .description attribute (ExtractedCompetency)
            # Check existence using a composite key assumption or just random ID if needed.
            # The schema uses 'id' as primary key.
            comp_id = f"{curriculum_id}-c{i}"
            
            exists_c = conn.execute(
                text("SELECT 1 FROM competencies WHERE id = :id"),
                {"id": comp_id}
            ).fetchone()
            
            if not exists_c:
                conn.execute(
                    text("""
                        INSERT INTO competencies (id, curriculum_id, title, description, order_index)
                        VALUES (:id, :cid, :title, :desc, :idx)
                    """),
                    {
                        "id": comp_id,
                        "cid": curriculum_id,
                        "title": comp.title,
                        "desc": comp.description or "",
                        "idx": i
                    }
                )

# --- Phase 3 Services ---
from sqlalchemy import text
import uuid

def store_standardized_competencies(curriculum_id: str, standardized_list: List[StandardizedCompetency]):
    """
    Idempotent insert of standardized competencies for a curriculum.
    """
    engine = create_engine(DATABASE_URL) # create new engine instance to avoid sharing issues or use global
    with engine.begin() as conn:
        for sc in standardized_list:
            exists = conn.execute(
                text("SELECT 1 FROM standardized_competencies WHERE standardized_id = :sid"),
                {"sid": sc.standardized_id}
            ).fetchone()
            
            if not exists:
                conn.execute(
                    text("""
                        INSERT INTO standardized_competencies (standardized_id, curriculum_id, original_text, standardized_text,
                          action_verb, content, context, bloom_level, complexity_level, source_chunk_id, extraction_confidence, llm_provenance)
                        VALUES (:sid, :cid, :orig, :std, :verb, :content, :context, :bloom, :complex, :chunk, :conf, :prov)
                    """),
                    {
                        "sid": sc.standardized_id,
                        "cid": curriculum_id,
                        "orig": sc.original_text,
                        "std": sc.standardized_text,
                        "verb": sc.action_verb,
                        "content": sc.content,
                        "context": sc.context,
                        "bloom": sc.bloom_level,
                        "complex": sc.complexity_level,
                        "chunk": sc.source_chunk_id,
                        "conf": sc.extraction_confidence,
                        "prov": json.dumps(sc.llm_provenance or {})
                    }
                )

def store_competency_metadata(metadata_map: Dict[str, CompetencyMetadata]):
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        for sid, meta in metadata_map.items():
            exists = conn.execute(
                text("SELECT 1 FROM competency_metadata WHERE standardized_id = :sid"),
                {"sid": sid}
            ).fetchone()
            
            if not exists:
                conn.execute(
                    text("""
                        INSERT INTO competency_metadata (id, standardized_id, subject, grade_level, domain, confidence_score, tags, llm_provenance)
                        VALUES (:id, :sid, :subject, :grade, :domain, :conf, :tags, :prov)
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "sid": sid,
                        "subject": meta.subject,
                        "grade": meta.grade_level,
                        "domain": meta.domain,
                        "conf": meta.confidence_score,
                        "tags": json.dumps(meta.tags or []),
                        "prov": json.dumps(meta.llm_provenance or {})
                    }
                )

# --- Phase 3 Admin Helpers ---

def list_pending_jobs(limit: int = 100):
    # This assumes IngestionJob model exists and has these fields
    # In a real app we would query the ORM model
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # Check if table exists first (for robustness in dev env)
        try:
             # Basic SQL since we haven't fully defined ORM mappings for pending reason in prev steps
             rows = conn.execute(text("SELECT id, source_url, status, created_at FROM ingestion_jobs WHERE status = 'pending_manual_review' LIMIT :limit"), {"limit": limit}).fetchall()
        except Exception:
             return []

        result = []
        for r in rows:
            # map row to dict
            result.append({
                "job_id": str(r[0]), # id
                "source_url": r[1],
                "requested_by": "system", # column missing in minimal schema
                "decision_reason": "Manual Review Required", # column missing in minimal schema
                "created_at": str(r[3])
            })
        return result

def approve_ingestion_job(job_id: str) -> bool:
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE ingestion_jobs SET status = 'approved' WHERE id = :id"),
            {"id": job_id}
        )
    # In strict implementation we would enqueue job here
    from .worker import enqueue_ingest_job
    # fetch url to re-queue
    # simplified for now
    return True

def reject_ingestion_job(job_id: str) -> bool:
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE ingestion_jobs SET status = 'rejected' WHERE id = :id"),
            {"id": job_id}
        )
    return True

def enqueue_ingest_job(url: str, requested_by: str):
    # Placeholder for RQ/Celery enqueue
    pass
