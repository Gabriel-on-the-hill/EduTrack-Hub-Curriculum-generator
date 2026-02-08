"""
Unit tests for EduTrack schemas.

Tests verify:
1. Valid data is accepted
2. Invalid data raises ValidationError
3. Blueprint rules are enforced (confidence thresholds, grounding, etc.)

Per Execution Protocol: All tests must pass before proceeding.
"""

from datetime import date, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.schemas.request import NormalizedRequest, NormalizedFields
from src.schemas.jurisdiction import JurisdictionResolution, JurisdictionInfo
from src.schemas.vault import VaultLookupResult
from src.schemas.agents import (
    ScoutOutput,
    GatekeeperOutput,
    ArchitectOutput,
    EmbedderOutput,
    CandidateUrl,
    ApprovedSource,
    CurriculumSnapshot,
    CompetencyItem,
)
from src.schemas.generation import (
    GenerationRequest,
    GenerationOutput,
    Citation,
    SourceAttribution,
)
from src.schemas.base import CurriculumMode
from src.schemas.curriculum import Curriculum, Competency
from src.schemas.base import (
    JurisdictionLevel,
    AssumptionType,
    CurriculumStatus,
    AgentStatus,
    AuthorityHint,
    VaultSource,
    GenerationRequestType,
    LicenseType,
)


# =============================================================================
# NORMALIZED REQUEST TESTS (Section 13.1)
# =============================================================================

class TestNormalizedRequest:
    """Tests for NormalizedRequest schema."""

    def test_valid_request(self) -> None:
        """Valid request should be accepted."""
        request = NormalizedRequest(
            request_id=uuid4(),
            raw_prompt="Grade 9 Biology for Nigeria",
            normalized=NormalizedFields(
                country="Nigeria",
                country_code="NG",
                grade="Grade 9",
                subject="Biology",
            ),
            confidence=0.95,
        )
        assert request.confidence == 0.95

    def test_rejects_low_confidence(self) -> None:
        """Request with confidence < 0.7 should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            NormalizedRequest(
                request_id=uuid4(),
                raw_prompt="test",
                normalized=NormalizedFields(
                    country="Nigeria",
                    country_code="NG",
                    grade="Grade 9",
                    subject="Biology",
                ),
                confidence=0.65,  # Below 0.7 threshold
            )
        assert "0.7" in str(exc_info.value)

    def test_rejects_invalid_country_code(self) -> None:
        """Invalid ISO-2 country code should be rejected."""
        with pytest.raises(ValidationError):
            NormalizedRequest(
                request_id=uuid4(),
                raw_prompt="test",
                normalized=NormalizedFields(
                    country="Nigeria",
                    country_code="NIG",  # Should be 2 letters
                    grade="Grade 9",
                    subject="Biology",
                ),
                confidence=0.9,
            )


# =============================================================================
# JURISDICTION RESOLUTION TESTS (Section 13.2)
# =============================================================================

class TestJurisdictionResolution:
    """Tests for JurisdictionResolution schema."""

    def test_valid_national_assumption(self) -> None:
        """Low JAS with assumed type should be valid for national."""
        resolution = JurisdictionResolution(
            request_id=uuid4(),
            jurisdiction=JurisdictionInfo(level=JurisdictionLevel.NATIONAL),
            jas_score=0.3,
            assumption_type=AssumptionType.ASSUMED,
            confidence=0.85,
        )
        assert resolution.jas_score == 0.3

    def test_rejects_high_jas_with_assumption(self) -> None:
        """JAS > 0.7 with assumed type should be INVALID."""
        with pytest.raises(ValidationError) as exc_info:
            JurisdictionResolution(
                request_id=uuid4(),
                jurisdiction=JurisdictionInfo(level=JurisdictionLevel.STATE),
                jas_score=0.8,  # Above 0.7
                assumption_type=AssumptionType.ASSUMED,  # Cannot assume with high JAS
                confidence=0.85,
            )
        assert "INVALID" in str(exc_info.value)

    def test_rejects_low_confidence(self) -> None:
        """Confidence < 0.6 should require user clarification."""
        with pytest.raises(ValidationError) as exc_info:
            JurisdictionResolution(
                request_id=uuid4(),
                jurisdiction=JurisdictionInfo(level=JurisdictionLevel.NATIONAL),
                jas_score=0.3,
                assumption_type=AssumptionType.ASSUMED,
                confidence=0.5,  # Below 0.6
            )
        assert "clarification" in str(exc_info.value).lower()


# =============================================================================
# VAULT LOOKUP TESTS (Section 13.3)
# =============================================================================

class TestVaultLookupResult:
    """Tests for VaultLookupResult schema."""

    def test_found_with_high_confidence(self) -> None:
        """Found curriculum with high confidence should serve immediately."""
        result = VaultLookupResult(
            request_id=uuid4(),
            found=True,
            curriculum_id=uuid4(),
            confidence=0.92,
            source=VaultSource.CACHE,
        )
        assert result.should_serve_immediately() is True
        assert result.should_warn_and_offer_refresh() is False

    def test_found_with_low_confidence(self) -> None:
        """Found curriculum with low confidence should warn."""
        result = VaultLookupResult(
            request_id=uuid4(),
            found=True,
            curriculum_id=uuid4(),
            confidence=0.75,
            source=VaultSource.CACHE,
        )
        assert result.should_serve_immediately() is False
        assert result.should_warn_and_offer_refresh() is True

    def test_not_found_triggers_cold_start(self) -> None:
        """Not found should trigger cold start job."""
        result = VaultLookupResult(
            request_id=uuid4(),
            found=False,
        )
        assert result.should_enqueue_cold_start() is True


# =============================================================================
# SCOUT AGENT TESTS (Section 13.4)
# =============================================================================

class TestScoutOutput:
    """Tests for ScoutOutput schema."""

    def test_valid_scout_output(self) -> None:
        """Valid scout output should be accepted."""
        output = ScoutOutput(
            job_id=uuid4(),
            queries=["biology curriculum nigeria"],
            candidate_urls=[
                CandidateUrl(
                    url="https://education.gov.ng/curriculum.pdf",
                    domain="education.gov.ng",
                    rank=1,
                    authority_hint=AuthorityHint.OFFICIAL,
                )
            ],
            status=AgentStatus.SUCCESS,
        )
        assert len(output.candidate_urls) == 1

    def test_rejects_too_many_queries(self) -> None:
        """More than 5 queries should be rejected."""
        with pytest.raises(ValidationError):
            ScoutOutput(
                job_id=uuid4(),
                queries=["q1", "q2", "q3", "q4", "q5", "q6"],  # 6 queries
                candidate_urls=[
                    CandidateUrl(
                        url="https://example.com",
                        domain="example.com",
                        rank=1,
                        authority_hint=AuthorityHint.UNKNOWN,
                    )
                ],
                status=AgentStatus.SUCCESS,
            )

    def test_rejects_success_with_no_urls(self) -> None:
        """Success status with no URLs should be rejected."""
        with pytest.raises(ValidationError):
            ScoutOutput(
                job_id=uuid4(),
                queries=["test query"],
                candidate_urls=[],  # No URLs
                status=AgentStatus.SUCCESS,  # But claims success
            )


# =============================================================================
# GENERATION OUTPUT TESTS (Section 13.9)
# =============================================================================

class TestGenerationOutput:
    """Tests for GenerationOutput schema - STRICTLY ENFORCED."""

    def test_valid_generation(self) -> None:
        """Valid generation with good coverage should be accepted."""
        output = GenerationOutput(
            output_id=uuid4(),
            content="# Lesson Plan\n\nObjectives...",
            citations=[
                Citation(competency_id=uuid4(), page_range="10-15")
            ],
            coverage=0.92,
            source_attribution=SourceAttribution(
                source_url="https://nerdc.gov.ng/biology.pdf",
                curriculum_mode=CurriculumMode.K12,
            ),
            status=AgentStatus.APPROVED,
        )
        assert output.is_grounded() is True

    def test_rejects_low_coverage_approved(self) -> None:
        """Approved status with coverage < 0.8 should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            GenerationOutput(
                output_id=uuid4(),
                content="Some content",
                citations=[
                    Citation(competency_id=uuid4(), page_range="1-5")
                ],
                coverage=0.75,  # Below 0.8
                source_attribution=SourceAttribution(
                    source_url="https://example.com/syllabus.pdf",
                    curriculum_mode=CurriculumMode.SYLLABUS,
                    institution="Example University",
                ),
                status=AgentStatus.APPROVED,  # Cannot be approved
            )
        assert "0.8" in str(exc_info.value)

    def test_rejects_no_citations(self) -> None:
        """Generation with no citations should be rejected."""
        with pytest.raises(ValidationError):
            GenerationOutput(
                output_id=uuid4(),
                content="Some content",
                citations=[],  # min_length=1 violated
                coverage=0.9,
                status=AgentStatus.APPROVED,
            )


# =============================================================================
# CURRICULUM MODEL TESTS (Section 3.1)
# =============================================================================

class TestCurriculum:
    """Tests for Curriculum data model."""

    def test_valid_curriculum(self) -> None:
        """Valid curriculum should be accepted."""
        curriculum = Curriculum(
            id=uuid4(),
            country="Nigeria",
            country_code="NG",
            jurisdiction_level=JurisdictionLevel.NATIONAL,
            grade="Grade 9",
            subject="Biology",
            status=CurriculumStatus.ACTIVE,
            confidence_score=0.92,
            last_verified=date.today(),
            ttl_expiry=date(2026, 7, 15),
        )
        assert curriculum.can_serve() is True

    def test_stale_curriculum_cannot_serve(self) -> None:
        """Stale curriculum should not be directly served."""
        curriculum = Curriculum(
            id=uuid4(),
            country="Nigeria",
            country_code="NG",
            jurisdiction_level=JurisdictionLevel.NATIONAL,
            grade="Grade 9",
            subject="Biology",
            status=CurriculumStatus.STALE,
            confidence_score=0.92,
            last_verified=date.today(),
            ttl_expiry=date(2026, 7, 15),
        )
        assert curriculum.can_serve() is False
