
import pytest
from src.ingestion import services
from src.ingestion import worker

def test_imports():
    assert services.store_standardized_competencies is not None
    assert worker.ingest_sync is not None
