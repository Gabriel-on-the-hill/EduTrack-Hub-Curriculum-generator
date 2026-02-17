# tests/services/test_store_curriculum_idempotent.py
import os
import json
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
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:") 
    init_db()
    comps = make_competencies()
    # just basic run check
    store_curriculum_and_chunks(comps)
