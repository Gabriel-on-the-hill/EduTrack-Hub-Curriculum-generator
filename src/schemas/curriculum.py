"""
Curriculum Data Model (Blueprint Section 3.1)

This module defines the canonical curriculum table structure and related models.
These are the core data models stored in Supabase.
"""

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field

from src.schemas.base import (
    ConfidenceScore,
    CountryCode,
    CurriculumStatus,
    JurisdictionLevel,
    NonEmptyStr,
    PageRange,
)


class Competency(BaseModel):
    """
    A single competency within a curriculum.
    
    Represents an atomic learning objective that can be traced
    back to the source document.
    """
    id: UUID = Field(description="Unique identifier")
    curriculum_id: UUID = Field(description="Parent curriculum UUID")
    title: NonEmptyStr = Field(description="Competency title")
    description: NonEmptyStr = Field(description="Full description")
    learning_outcomes: list[NonEmptyStr] = Field(
        min_length=1,
        description="Specific, measurable outcomes"
    )
    page_range: PageRange = Field(description="Source document pages")
    source_chunk_ids: list[UUID] = Field(
        min_length=1,
        description="IDs of source chunks this competency maps to"
    )
    confidence: ConfidenceScore = Field(description="Extraction confidence")

    def is_grounded(self) -> bool:
        """
        Check if competency is fully grounded in source material.
        
        Per Blueprint Section 20.1: Every competency must reference
        at least 1 source chunk ID.
        """
        return len(self.source_chunk_ids) >= 1


class Curriculum(BaseModel):
    """
    Canonical Curriculum Model (Blueprint Section 3.1).
    
    This is the primary data structure stored in the vault.
    All fields are required as specified in the Blueprint.
    """
    id: UUID = Field(description="Unique identifier")
    
    # Geographic information
    country: NonEmptyStr = Field(description="Human-readable country name")
    country_code: CountryCode = Field(description="ISO-2 country code")
    
    # Jurisdiction hierarchy
    jurisdiction_level: JurisdictionLevel = Field(
        description="national, state, or county"
    )
    jurisdiction_name: str | None = Field(
        default=None,
        description="Name of specific jurisdiction (null for national)"
    )
    parent_jurisdiction_id: UUID | None = Field(
        default=None,
        description="UUID of parent jurisdiction (null for top-level)"
    )
    
    # Educational classification
    grade: NonEmptyStr = Field(description="Normalized grade level")
    subject: NonEmptyStr = Field(description="Canonical subject name")
    
    # Status and confidence
    status: CurriculumStatus = Field(
        description="active, stale, or conflicted"
    )
    confidence_score: ConfidenceScore = Field(
        description="Overall confidence in the curriculum data"
    )
    
    # Temporal metadata
    last_verified: date = Field(description="Date of last verification")
    ttl_expiry: date = Field(description="Date when curriculum should be re-verified")
    
    # Source tracking
    source_url: NonEmptyStr | None = Field(
        default=None,
        description="URL of the official source document"
    )
    source_authority: NonEmptyStr | None = Field(
        default=None,
        description="Name of the issuing authority"
    )

    def is_fresh(self, current_date: date) -> bool:
        """Check if curriculum is within TTL."""
        return current_date < self.ttl_expiry

    def needs_refresh(self, current_date: date) -> bool:
        """Check if curriculum is stale or expired."""
        return self.status == CurriculumStatus.STALE or current_date >= self.ttl_expiry

    def can_serve(self) -> bool:
        """Check if curriculum can be served to users."""
        return (
            self.status == CurriculumStatus.ACTIVE 
            and self.confidence_score >= 0.8
        )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "987e6543-e21b-12d3-a456-426614174000",
                    "country": "Nigeria",
                    "country_code": "NG",
                    "jurisdiction_level": "national",
                    "jurisdiction_name": None,
                    "parent_jurisdiction_id": None,
                    "grade": "Grade 9",
                    "subject": "Biology",
                    "status": "active",
                    "confidence_score": 0.92,
                    "last_verified": "2026-01-15",
                    "ttl_expiry": "2026-07-15",
                    "source_url": "https://education.gov.ng/curriculum/biology-9.pdf",
                    "source_authority": "Nigerian Educational Research Development Council"
                }
            ]
        }
    }
