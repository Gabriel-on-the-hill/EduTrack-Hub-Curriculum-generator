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


def store_curriculum_and_chunks(competencies):
    session = SessionLocal()
    for comp in competencies:
        chunk = CurriculumChunk(
            content=comp.title,
            metadata={"source_chunk_id": comp.source_chunk_id},
        )
        session.add(chunk)
    session.commit()
    session.close()
