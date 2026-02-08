"""
Generation Schemas (Blueprint Sections 13.8-13.9)

This module defines the input and output schemas for content generation:
- Generation Request (13.8): Input for lesson/quiz/summary generation
- Generation Output (13.9): Strictly enforced output with coverage requirements

Rules (from Blueprint Section 9 - Generation Guardrails):
- coverage < 0.8 → rejected
- citations.length = 0 → rejected
"""

from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from src.schemas.base import (
    AgentStatus,
    ConfidenceScore,
    CurriculumMode,
    GenerationRequestType,
    NonEmptyStr,
    PageRange,
)


# =============================================================================
# GENERATION REQUEST (Section 13.8)
# =============================================================================

class GenerationConstraints(BaseModel):
    """Constraints for content generation."""
    duration: NonEmptyStr | None = Field(
        default=None,
        description="Target duration (e.g., '45 minutes', '1 hour')"
    )
    offline_friendly: bool = Field(
        default=False,
        description="Whether content should work offline"
    )
    difficulty_level: NonEmptyStr | None = Field(
        default=None,
        description="Target difficulty (e.g., 'beginner', 'intermediate')"
    )
    language: NonEmptyStr = Field(
        default="English",
        description="Output language"
    )


class GenerationRequest(BaseModel):
    """
    Input for Generation (13.8).
    
    Specifies what type of content to generate and any constraints.
    """
    curriculum_id: UUID = Field(
        description="UUID of the curriculum to generate from"
    )
    request_type: GenerationRequestType = Field(
        description="Type: lesson_plan, quiz, or summary"
    )
    competency_ids: list[UUID] | None = Field(
        default=None,
        description="Specific competencies to cover (null = all)"
    )
    constraints: GenerationConstraints = Field(
        default_factory=GenerationConstraints,
        description="Optional constraints for generation"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "curriculum_id": "987e6543-e21b-12d3-a456-426614174000",
                    "request_type": "lesson_plan",
                    "constraints": {
                        "duration": "45 minutes",
                        "offline_friendly": True
                    }
                }
            ]
        }
    }


# =============================================================================
# GENERATION OUTPUT (Section 13.9 - Strictly Enforced)
# =============================================================================

class Citation(BaseModel):
    """A citation linking generated content to source material."""
    competency_id: UUID = Field(
        description="UUID of the competency being cited"
    )
    page_range: PageRange = Field(
        description="Page range in the source document"
    )


class SourceAttribution(BaseModel):
    """
    Mandatory source attribution for generated content.
    
    Per verdict: Every generated artifact must include:
    "Based on the syllabus from: Institution · Department · Course · URL"
    If missing → generation fails. No exceptions.
    """
    source_url: NonEmptyStr = Field(
        description="URL of the source document"
    )
    institution: str | None = Field(
        default=None,
        description="Institution name (for university mode)"
    )
    department: str | None = Field(
        default=None,
        description="Department name (for university mode)"
    )
    course: str | None = Field(
        default=None,
        description="Course name or code"
    )
    curriculum_mode: CurriculumMode = Field(
        description="K12 for canonical curriculum, SYLLABUS for university"
    )
    disclaimer: str | None = Field(
        default=None,
        description="Auto-generated disclaimer for university content"
    )
    
    def format_attribution(self) -> str:
        """Format the attribution for display."""
        if self.curriculum_mode == CurriculumMode.K12:
            return f"Based on official curriculum from: {self.source_url}"
        else:
            parts = ["Based on syllabus from:"]
            if self.institution:
                parts.append(self.institution)
            if self.department:
                parts.append(f"· {self.department}")
            if self.course:
                parts.append(f"· {self.course}")
            parts.append(f"· {self.source_url}")
            return " ".join(parts)


class GenerationOutput(BaseModel):
    """
    Output of Generation (13.9 - Strictly Enforced).
    
    Blueprint Section 9 (Generation Guardrails):
    - coverage < 0.8 → rejected
    - citations.length = 0 → rejected
    - source_attribution missing → rejected (verdict requirement)
    
    Every generated paragraph MUST map to at least one source.
    """
    output_id: UUID = Field(
        description="Unique identifier for this generation"
    )
    content: NonEmptyStr = Field(
        description="The generated content (lesson plan, quiz, or summary)"
    )
    citations: list[Citation] = Field(
        min_length=1,
        description="Citations linking content to sources (at least 1 required)"
    )
    coverage: ConfidenceScore = Field(
        description="Coverage of requested competencies (0.0-1.0)"
    )
    source_attribution: SourceAttribution = Field(
        description="Mandatory source attribution - required for all outputs"
    )
    status: AgentStatus = Field(
        description="approved or rejected"
    )

    @model_validator(mode="after")
    def enforce_generation_guardrails(self) -> "GenerationOutput":
        """
        Enforce Blueprint Section 9 Generation Guardrails:
        - coverage < 0.8 → rejected
        - citations.length = 0 → rejected (handled by min_length=1)
        
        These are STRICT requirements. No exceptions.
        """
        # Rule 1: Coverage must be >= 0.8
        if self.coverage < 0.8:
            if self.status == AgentStatus.APPROVED:
                raise ValueError(
                    f"Generation coverage {self.coverage} < 0.8 but status is 'approved'. "
                    f"Blueprint Section 9 requires coverage >= 0.8. Must be 'rejected'."
                )
        
        # Rule 2: Approved content must have sufficient coverage
        if self.status == AgentStatus.APPROVED and self.coverage < 0.8:
            raise ValueError(
                f"Cannot approve generation with coverage {self.coverage} < 0.8"
            )
        
        return self

    def is_grounded(self) -> bool:
        """
        Check if generation meets Blueprint grounding requirements.
        
        Section 20.1: Grounding = 1.0 (binary) for storage.
        """
        return self.coverage >= 0.8 and len(self.citations) > 0

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "output_id": "aaa11111-e89b-12d3-a456-426614174000",
                    "content": "# Lesson: Cell Division\n\n## Objectives...",
                    "citations": [
                        {
                            "competency_id": "bbb22222-e89b-12d3-a456-426614174000",
                            "page_range": "10-15"
                        }
                    ],
                    "coverage": 0.92,
                    "status": "approved"
                }
            ]
        }
    }
