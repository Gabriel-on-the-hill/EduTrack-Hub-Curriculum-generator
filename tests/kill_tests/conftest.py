"""
Kill Test Fixtures (Phase 6)

Standardized environment for all kill tests.
Enforces:
- Read-only database access
- Deterministic embedding stubs
- Production harness instantiation
"""

import pytest
from unittest.mock import MagicMock, Mock
from sqlalchemy import create_engine
from typing import Generator

from src.production.harness import ProductionHarness, ModelProvenance
from src.production.embeddings import MockEmbeddingProvider
from src.production.security import ReadOnlySession

# MOCK CONNECTION STRING - In real CI, this would be the read-only user URL
READONLY_CONNECTION_STRING = "sqlite:///:memory:" 

@pytest.fixture
def binding_specs():
    """Access to configured thresholds."""
    from config import kill_test_thresholds
    return kill_test_thresholds

@pytest.fixture
def embedding_stub():
    """Deterministic local embeddings for content delta testing."""
    return MockEmbeddingProvider(model_name="kill-test-stub")

@pytest.fixture
def mock_db_session():
    """
    Simulates a ReadOnlySession for unit-level kill tests.
    For KT-A4 (End-to-End DB Role), we will use a separate raw connection.
    """
    session = MagicMock(spec=ReadOnlySession)
    # Configure session to look like a valid read-only session
    session.__class__ = ReadOnlySession 
    return session

@pytest.fixture
def harness(mock_db_session, embedding_stub):
    """
    ProductionHarness configured for Kill Tests.
    - ReadOnlySession injected
    - MockEmbeddingProvider injected
    - DB Level verification DISABLED for unit/logic tests (enabled for integration)
    """
    return ProductionHarness(
        db_session=mock_db_session,
        embedding_provider=embedding_stub,
        primary_provenance=ModelProvenance(model_id="kill-test-primary", rng_seed=42),
        shadow_provenance=ModelProvenance(model_id="kill-test-shadow", rng_seed=42),
        verify_db_level=False, # Disabled by default, enabled explicitly in KT-A tests
        storage_path="./kill_test_logs" # Local persistence
    )

@pytest.fixture
def seeded_curriculum():
    """
    Returns a consistent curriculum object for deterministic testing.
    Represents a verified Phase 4 artifact.
    """
    from src.synthetic.schemas import SyntheticCurriculumOutput, SyntheticCurriculumConfig, GroundTruth
    syn_config = SyntheticCurriculumConfig(
        synthetic_id="kill-test",
        ground_truth=GroundTruth(expected_grade="9", expected_subject="Biology", expected_jurisdiction="national")
    )
    return SyntheticCurriculumOutput(
        config=syn_config,
        content_markdown="# Cell Division\n\n## Mitosis\nMitosis is the process...",
        metrics={},
        metadata={"provenance": {"source_authority": "National Board"}}
    )

@pytest.fixture
def valid_provenance():
    """Valid provenance dictionary for passing governance checks."""
    return {
        "curriculum_id": "test-curriculum-id",
        "source_list": [
            {"url": "http://example.com", "authority": "Valid Authority", "fetch_date": "2026-01-01"}
        ],
        "retrieval_timestamp": "2026-01-01T00:00:00Z",
        "extraction_confidence": 1.0
    }
