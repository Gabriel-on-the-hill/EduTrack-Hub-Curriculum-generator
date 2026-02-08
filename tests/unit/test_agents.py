"""
Unit tests for ingestion agents.

Tests verify:
1. Scout agent query generation and URL ranking
2. Gatekeeper source validation and conflict detection
3. Architect PDF parsing and competency extraction
4. Embedder chunk creation
"""

from datetime import date
from uuid import uuid4

import pytest

from src.schemas.agents import CandidateUrl
from src.schemas.base import AgentStatus, AuthorityHint, LicenseType


class TestScoutAgent:
    """Tests for Scout agent."""

    def test_query_generation(self) -> None:
        """Should generate max 5 search queries."""
        from src.agents.scout import ScoutAgent
        
        agent = ScoutAgent()
        queries = agent._generate_queries("Nigeria", "Grade 9", "Biology")
        
        assert len(queries) <= 5
        assert all("Nigeria" in q or "nigeria" in q.lower() for q in queries)

    def test_authority_detection_official(self) -> None:
        """Should detect official government domains."""
        from src.agents.scout import ScoutAgent
        
        agent = ScoutAgent()
        
        # Nigerian government
        hint = agent._detect_authority(
            "https://nerdc.gov.ng/curriculum.pdf",
            "NG"
        )
        assert hint == AuthorityHint.OFFICIAL
        
        # Kenyan government
        hint = agent._detect_authority(
            "https://kicd.ac.ke/curriculum.pdf",
            "KE"
        )
        assert hint == AuthorityHint.OFFICIAL

    def test_authority_detection_unknown(self) -> None:
        """Should mark unknown sources correctly."""
        from src.agents.scout import ScoutAgent
        
        agent = ScoutAgent()
        hint = agent._detect_authority(
            "https://random-site.com/curriculum.pdf",
            "NG"
        )
        assert hint == AuthorityHint.UNKNOWN

    @pytest.mark.asyncio
    async def test_search_returns_results(self) -> None:
        """Search should return candidate URLs."""
        from src.agents.scout import run_scout
        
        result = await run_scout(
            country="Nigeria",
            country_code="NG",
            grade="Grade 9",
            subject="Biology",
        )
        
        assert result.status == AgentStatus.SUCCESS
        assert len(result.candidate_urls) > 0
        assert len(result.queries) <= 5


class TestGatekeeperAgent:
    """Tests for Gatekeeper agent."""

    @pytest.mark.asyncio
    async def test_validates_official_sources(self) -> None:
        """Should approve official sources."""
        from src.agents.gatekeeper import run_gatekeeper
        
        candidates = [
            CandidateUrl(
                url="https://nerdc.gov.ng/biology-2019.pdf",
                domain="nerdc.gov.ng",
                rank=1,
                authority_hint=AuthorityHint.OFFICIAL,
            )
        ]
        
        result = await run_gatekeeper(candidates, "Nigeria", "NG")
        
        assert result.status == AgentStatus.SUCCESS
        assert len(result.approved_sources) == 1
        assert result.approved_sources[0].license == LicenseType.GOVERNMENT

    @pytest.mark.asyncio
    async def test_rejects_unknown_license(self) -> None:
        """Should reject sources with unknown license."""
        from src.agents.gatekeeper import run_gatekeeper
        
        candidates = [
            CandidateUrl(
                url="https://unknown-site.com/curriculum.pdf",
                domain="unknown-site.com",
                rank=1,
                authority_hint=AuthorityHint.UNKNOWN,
            )
        ]
        
        result = await run_gatekeeper(candidates, "Nigeria", "NG")
        
        # Should fail because unknown license
        assert result.status == AgentStatus.FAILED
        assert len(result.approved_sources) == 0

    @pytest.mark.asyncio
    async def test_empty_candidates_fails(self) -> None:
        """Should fail with no candidates."""
        from src.agents.gatekeeper import run_gatekeeper
        
        result = await run_gatekeeper([], "Nigeria", "NG")
        
        assert result.status == AgentStatus.FAILED


class TestArchitectAgent:
    """Tests for Architect agent."""

    def test_checksum_computation(self) -> None:
        """Should compute valid SHA-256 checksums."""
        from src.agents.architect import ArchitectAgent
        import tempfile
        from pathlib import Path
        
        agent = ArchitectAgent()
        
        # Create temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"test content")
            temp_path = Path(f.name)
        
        try:
            checksum = agent._compute_checksum(temp_path)
            assert len(checksum) == 64  # SHA-256 hex
            assert checksum.isalnum()
        finally:
            temp_path.unlink()

    def test_rule_based_extraction(self) -> None:
        """Should extract competencies using patterns."""
        from src.agents.architect import ArchitectAgent
        
        agent = ArchitectAgent()
        
        text = """
        Competency 1.1: Cell Structure
        Students will understand cells.
        - Identify cell parts
        - Describe organelles
        
        Competency 1.2: Cell Division
        Students will learn mitosis.
        - Explain stages
        """
        
        competencies = agent._rule_based_extraction(text)
        
        assert len(competencies) >= 2
        assert any("Cell" in c.title for c in competencies)


class TestEmbedderAgent:
    """Tests for Embedder agent."""

    def test_chunk_creation(self) -> None:
        """Should create chunks from competencies."""
        from src.agents.embedder import EmbedderAgent
        from src.schemas.agents import CompetencyItem
        
        agent = EmbedderAgent()
        
        competencies = [
            CompetencyItem(
                competency_id=uuid4(),
                title="Test Competency",
                description="This is a test description.",
                learning_outcomes=["Outcome 1", "Outcome 2"],
                page_range="1-5",
                confidence=0.9,
            )
        ]
        
        chunks = agent._create_chunks(competencies)
        
        assert len(chunks) >= 1
        assert chunks[0].competency_id == competencies[0].competency_id

    @pytest.mark.asyncio
    async def test_embed_empty_fails(self) -> None:
        """Should fail with no competencies."""
        from src.agents.embedder import run_embedder
        
        result = await run_embedder(uuid4(), [])
        
        assert result.status == AgentStatus.FAILED
        assert result.embedded_chunks == 0

    @pytest.mark.asyncio
    async def test_embed_success(self) -> None:
        """Should succeed with valid competencies."""
        from src.agents.embedder import run_embedder
        from src.schemas.agents import CompetencyItem
        
        competencies = [
            CompetencyItem(
                competency_id=uuid4(),
                title="Test",
                description="Test description",
                learning_outcomes=["Learn something"],
                page_range="1",
                confidence=0.85,
            )
        ]
        
        result = await run_embedder(uuid4(), competencies)
        
        assert result.status == AgentStatus.SUCCESS
        assert result.embedded_chunks > 0
