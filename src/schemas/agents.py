"""
Agent Output Schemas (Blueprint Sections 13.4-13.7)

This module defines the output schemas for all agent workers:
- Scout Agent (13.4): Search for curriculum sources
- Gatekeeper Agent (13.5): Validate source authority
- Architect Agent (13.6): Parse curriculum into competencies
- Embedder (13.7): Create vector embeddings
"""

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from src.schemas.base import (
    AgentStatus,
    AuthorityHint,
    ConfidenceScore,
    InstitutionType,
    LicenseType,
    NonEmptyStr,
    PageRange,
)


# =============================================================================
# SCOUT AGENT OUTPUT (Section 13.4)
# =============================================================================

class CandidateUrl(BaseModel):
    """A candidate URL found by the Scout agent."""
    url: NonEmptyStr = Field(description="Full URL of the candidate source")
    domain: NonEmptyStr = Field(description="Domain of the URL (e.g., 'education.gov.ng')")
    rank: int = Field(ge=1, description="Ranking of this candidate (1 = best)")
    authority_hint: AuthorityHint = Field(
        description="Hint about whether this is an official source"
    )


class ScoutOutput(BaseModel):
    """
    Output of Scout Agent (Search).
    
    Blueprint Section 13.4:
    - queries.length ≤ 5
    - candidate_urls.length ≥ 1 OR status = failed
    """
    job_id: UUID = Field(description="Unique identifier for this search job")
    queries: list[NonEmptyStr] = Field(
        max_length=5,
        description="Search queries used (max 5)"
    )
    candidate_urls: list[CandidateUrl] = Field(
        default_factory=list,
        description="Candidate URLs found"
    )
    status: AgentStatus = Field(description="success or failed")

    @model_validator(mode="after")
    def validate_results(self) -> "ScoutOutput":
        """
        Enforce Blueprint rules:
        - queries.length ≤ 5 (handled by max_length)
        - candidate_urls.length ≥ 1 OR status = failed
        """
        if len(self.candidate_urls) == 0 and self.status != AgentStatus.FAILED:
            raise ValueError(
                "Scout agent must have at least 1 candidate URL or status must be 'failed'"
            )
        return self


# =============================================================================
# GATEKEEPER AGENT OUTPUT (Section 13.5)
# =============================================================================

class ApprovedSource(BaseModel):
    """A source that has been validated by the Gatekeeper."""
    url: NonEmptyStr = Field(description="URL of the approved source")
    authority: NonEmptyStr = Field(description="Name of the issuing authority")
    license: LicenseType = Field(description="License status: permissive, unclear, or restricted")
    published_date: date = Field(description="Publication date of the document")
    confidence: ConfidenceScore = Field(description="Confidence in the validation")
    # University-specific field
    institution_type: InstitutionType = Field(
        default=InstitutionType.UNKNOWN,
        description="Trust tier: accredited, unknown, or training_provider"
    )


class GatekeeperOutput(BaseModel):
    """
    Output of Gatekeeper Agent (Validation).
    
    Blueprint Section 13.5:
    - approved_sources.length = 0 → failed
    - status = conflicted → require human alert
    """
    job_id: UUID = Field(description="Links to the Scout job")
    approved_sources: list[ApprovedSource] = Field(
        default_factory=list,
        description="Sources that passed validation"
    )
    rejected_sources: list[NonEmptyStr] = Field(
        default_factory=list,
        description="URLs that were rejected"
    )
    status: AgentStatus = Field(description="approved, conflicted, or failed")

    @model_validator(mode="after")
    def validate_results(self) -> "GatekeeperOutput":
        """
        Enforce Blueprint rules:
        - approved_sources.length = 0 → status must be failed
        """
        if len(self.approved_sources) == 0 and self.status not in [
            AgentStatus.FAILED, AgentStatus.CONFLICTED
        ]:
            raise ValueError(
                "Gatekeeper with no approved sources must have status 'failed' or 'conflicted'"
            )
        return self


# =============================================================================
# ARCHITECT AGENT OUTPUT (Section 13.6)
# =============================================================================

class CurriculumSnapshot(BaseModel):
    """Reference to the stored curriculum document."""
    file_path: NonEmptyStr = Field(description="Storage path (e.g., 's3://...')")
    checksum: NonEmptyStr = Field(description="SHA-256 checksum of the file")
    pages: int = Field(ge=0, description="Number of pages in the document")


class CompetencyItem(BaseModel):
    """A single competency extracted from the curriculum."""
    competency_id: UUID = Field(description="Unique identifier for this competency")
    title: NonEmptyStr = Field(description="Title of the competency")
    description: NonEmptyStr = Field(description="Full description")
    learning_outcomes: list[NonEmptyStr] = Field(
        min_length=1,
        description="Specific learning outcomes (at least 1)"
    )
    page_range: PageRange = Field(description="Page range where this appears")
    confidence: ConfidenceScore = Field(description="Extraction confidence")


class ArchitectOutput(BaseModel):
    """
    Output of Architect Agent (Parsing).
    
    Blueprint Section 13.6:
    - average_confidence < 0.75 → low_confidence
    - competencies.length = 0 → failed
    """
    job_id: UUID = Field(description="Links to the Gatekeeper job")
    curriculum_snapshot: CurriculumSnapshot = Field(
        description="Reference to the stored document"
    )
    competencies: list[CompetencyItem] = Field(
        default_factory=list,
        description="Extracted competencies"
    )
    average_confidence: ConfidenceScore = Field(
        description="Average confidence across all competencies"
    )
    status: AgentStatus = Field(description="success, low_confidence, or failed")

    @model_validator(mode="after")
    def validate_results(self) -> "ArchitectOutput":
        """
        Enforce Blueprint rules:
        - average_confidence < 0.75 → status should be low_confidence
        - competencies.length = 0 → status should be failed
        """
        if len(self.competencies) == 0 and self.status != AgentStatus.FAILED:
            raise ValueError(
                "Architect with no competencies must have status 'failed'"
            )
        
        if self.average_confidence < 0.75 and self.status == AgentStatus.SUCCESS:
            raise ValueError(
                f"Architect confidence {self.average_confidence} < 0.75 "
                f"but status is 'success' - should be 'low_confidence'"
            )
        
        return self


# =============================================================================
# EMBEDDER OUTPUT (Section 13.7)
# =============================================================================

class EmbedderOutput(BaseModel):
    """
    Output of Embedder.
    
    Blueprint Section 13.7:
    Creates vector embeddings for retrieval.
    """
    curriculum_id: UUID = Field(description="UUID of the curriculum being embedded")
    embedded_chunks: int = Field(ge=0, description="Number of chunks embedded")
    embedding_model: NonEmptyStr = Field(description="Name of the embedding model used")
    status: AgentStatus = Field(description="success or failed")

    @model_validator(mode="after")
    def validate_results(self) -> "EmbedderOutput":
        """Ensure chunks are embedded on success."""
        if self.embedded_chunks == 0 and self.status == AgentStatus.SUCCESS:
            raise ValueError(
                "Embedder with status 'success' must have at least 1 embedded chunk"
            )
        return self
