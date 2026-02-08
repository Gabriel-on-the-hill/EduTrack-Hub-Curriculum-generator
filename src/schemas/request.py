"""
Request Normalization Schema (Blueprint Section 13.1)

This schema defines the output of the Request Controller → Decision Engine.
It normalizes raw user prompts into structured, validated requests.

Validation rules (from Blueprint):
- confidence < 0.7 → reject request
- missing normalized fields → reject request
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from src.schemas.base import (
    ConfidenceScore,
    CountryCode,
    CurriculumMode,
    NonEmptyStr,
)


class NormalizedFields(BaseModel):
    """
    The normalized components extracted from a raw user prompt.
    
    All core fields are required - missing fields cause request rejection.
    Institution fields are optional (used for university mode).
    """
    country: NonEmptyStr = Field(
        description="Human-readable country name (e.g., 'Nigeria')"
    )
    country_code: CountryCode = Field(
        description="ISO-2 country code (e.g., 'NG' for Nigeria)"
    )
    grade: NonEmptyStr = Field(
        description="Normalized grade level (e.g., 'Grade 9', 'BSc Year 2')"
    )
    subject: NonEmptyStr = Field(
        description="Canonical subject name (e.g., 'Biology', 'Computer Science')"
    )
    language: NonEmptyStr = Field(
        default="English",
        description="Language of the curriculum (defaults to English)"
    )
    # University/college specific fields
    institution: str | None = Field(
        default=None,
        description="Institution name for university mode (e.g., 'MIT', 'Harvard')"
    )
    department: str | None = Field(
        default=None,
        description="Department/faculty name (e.g., 'Computer Science', 'Engineering')"
    )
    curriculum_mode: CurriculumMode = Field(
        default=CurriculumMode.K12,
        description="K12 for government curriculum, SYLLABUS for university"
    )


class NormalizedRequest(BaseModel):
    """
    Output of Request Normalization (Controller → Decision Engine).
    
    Blueprint Section 13.1:
    - confidence < 0.7 → reject request
    - missing normalized fields → reject request
    """
    request_id: UUID = Field(
        description="Unique identifier for this request"
    )
    raw_prompt: NonEmptyStr = Field(
        description="The original user input before normalization"
    )
    normalized: NormalizedFields = Field(
        description="Structured, validated fields extracted from the prompt"
    )
    confidence: ConfidenceScore = Field(
        description="Confidence score for the normalization (0.0-1.0)"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="ISO-8601 timestamp of when the request was processed"
    )

    @model_validator(mode="after")
    def validate_confidence_threshold(self) -> "NormalizedRequest":
        """
        Enforce minimum confidence threshold of 0.7.
        
        Per Blueprint: confidence < 0.7 → reject request
        """
        if self.confidence < 0.7:
            raise ValueError(
                f"Normalization confidence {self.confidence} is below "
                f"minimum threshold 0.7 - request must be rejected"
            )
        return self

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "request_id": "123e4567-e89b-12d3-a456-426614174000",
                    "raw_prompt": "Grade 9 Biology curriculum for Nigeria",
                    "normalized": {
                        "country": "Nigeria",
                        "country_code": "NG",
                        "grade": "Grade 9",
                        "subject": "Biology",
                        "language": "English"
                    },
                    "confidence": 0.95,
                    "timestamp": "2026-01-31T12:00:00Z"
                }
            ]
        }
    }
