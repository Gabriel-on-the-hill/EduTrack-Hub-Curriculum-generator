# tests/services/test_store_curriculum_idempotent.py
import os
import json
from sqlalchemy import create_engine, text
from src.ingestion.services import init_db, store_curriculum_and_chunks
from src.ingestion.schemas import ExtractedCompetency
from datetime import datetime
from pathlib import Path
import pytest

def make_competencies():
    return [
        ExtractedCompetency(
            title="Cell Division",
            description="Mitosis description",
            learning_outcomes=["Describe mitosis"],
            source_chunk_id="chunk_1"
        )
    ]

def test_store_curriculum_and_chunks(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}") 
    init_db()
    
    # Create the app-level tables that store_curriculum_and_chunks uses (raw SQL)
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS curricula (
                id TEXT PRIMARY KEY,
                country TEXT NOT NULL,
                grade TEXT NOT NULL,
                subject TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                source_authority TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS competencies (
                id TEXT PRIMARY KEY,
                curriculum_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                order_index INTEGER DEFAULT 0
            )
        """))
    
    comps = make_competencies()
    # Must pass curriculum_id, url, and competencies
    store_curriculum_and_chunks("test-curr-1", "http://example.com/curr.pdf", comps)

