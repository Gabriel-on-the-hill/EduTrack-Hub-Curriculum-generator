"""
University Curriculum Governance (Phase 4.2 Blueprint Update)

Implements governance controls for university/college curriculum support:
- Disclaimer generation (mandatory for university outputs)
- Provenance metadata (source URL, extraction date, confidence)
- Lower confidence thresholds for university content
- Staleness indicators

Binding Policy (from Engineering Reality Check):
- University curriculum support is PROVISIONALLY ENABLED
- Treat as "validated artifacts, not canonical truth"
- Do not expose higher-ed outputs publicly without visible provenance and disclaimers
"""

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from src.schemas.base import (
    ConfidenceScore,
    CurriculumMode,
    InstitutionType,
    NonEmptyStr,
)


# =============================================================================
# CONFIDENCE THRESHOLDS (University vs K-12)
# =============================================================================

class UniversityConfidenceThresholds:
    """
    Lower confidence thresholds for university content.
    
    University syllabi are less standardized than K-12 curricula,
    so we accept lower confidence while requiring additional disclaimers.
    """
    # Standard K-12 thresholds for comparison
    K12_SOURCE_VALIDATION: float = 0.90
    K12_EXTRACTION: float = 0.85
    
    # University thresholds (lower due to variability)
    UNIVERSITY_SOURCE_VALIDATION: float = 0.75
    UNIVERSITY_EXTRACTION: float = 0.70
    
    @classmethod
    def get_threshold(cls, mode: CurriculumMode, threshold_type: str) -> float:
        """Get appropriate threshold based on curriculum mode."""
        if mode == CurriculumMode.K12:
            thresholds = {
                "source_validation": cls.K12_SOURCE_VALIDATION,
                "extraction": cls.K12_EXTRACTION,
            }
        else:
            thresholds = {
                "source_validation": cls.UNIVERSITY_SOURCE_VALIDATION,
                "extraction": cls.UNIVERSITY_EXTRACTION,
            }
        return thresholds.get(threshold_type, 0.85)


class ContextualThresholds:
    """
    Contextual thresholds by request type (Fix #8).
    
    University thresholds vary by output type:
    - summary: 0.75 (lenient)
    - lesson_plan: 0.80
    - exam/objectives: 0.85 (stricter)
    - certification: 0.90 (most strict)
    
    K-12 thresholds are higher across the board.
    """
    
    K12_THRESHOLDS: dict[str, float] = {
        "summary": 0.85,
        "lesson_plan": 0.90,
        "quiz": 0.90,
        "exam": 0.90,
        "learning_objectives": 0.90,
        "certification": 0.95,
    }
    
    UNIVERSITY_THRESHOLDS: dict[str, float] = {
        "summary": 0.75,
        "lesson_plan": 0.80,
        "quiz": 0.85,
        "exam": 0.85,
        "learning_objectives": 0.85,
        "certification": 0.90,
    }
    
    @classmethod
    def get_threshold(cls, mode: CurriculumMode, request_type: str) -> float:
        """
        Get appropriate threshold for mode and request type.
        
        Args:
            mode: K12 or SYLLABUS
            request_type: Type of generation request
            
        Returns:
            Confidence threshold (0.0-1.0)
        """
        if mode == CurriculumMode.K12:
            return cls.K12_THRESHOLDS.get(request_type, 0.90)
        else:
            return cls.UNIVERSITY_THRESHOLDS.get(request_type, 0.80)
    
    @classmethod
    def check_threshold(
        cls, 
        mode: CurriculumMode, 
        request_type: str, 
        actual_confidence: float
    ) -> tuple[bool, float]:
        """
        Check if confidence meets threshold.
        
        Returns:
            Tuple of (passes, required_threshold)
        """
        threshold = cls.get_threshold(mode, request_type)
        return (actual_confidence >= threshold, threshold)


# =============================================================================
# DISCLAIMER GENERATION
# =============================================================================

class DisclaimerLevel(str, Enum):
    """Level of disclaimer required."""
    NONE = "none"           # Official K-12 curriculum
    STANDARD = "standard"   # University syllabus
    ENHANCED = "enhanced"   # Unverified institution
    MAXIMUM = "maximum"     # Training provider / unknown


# Pre-defined disclaimer templates
DISCLAIMER_TEMPLATES = {
    DisclaimerLevel.NONE: None,
    
    DisclaimerLevel.STANDARD: (
        "This content is based on an extracted syllabus, not an authoritative curriculum. "
        "Course content may vary by semester, instructor, or section. "
        "Always verify with your institution's official materials."
    ),
    
    DisclaimerLevel.ENHANCED: (
        "⚠️ This content is extracted from an educational syllabus whose institution "
        "accreditation status could not be verified. Content accuracy is not guaranteed. "
        "This is provided for reference only and should not be relied upon for academic purposes."
    ),
    
    DisclaimerLevel.MAXIMUM: (
        "⚠️ UNVERIFIED SOURCE: This content is extracted from an unverified training provider. "
        "No claims are made about accuracy, completeness, or educational validity. "
        "Use at your own risk. This is NOT from an accredited educational institution."
    ),
}


class DisclaimerGenerator:
    """
    Generates appropriate disclaimers based on curriculum type and source.
    
    Policy: Do not expose higher-ed outputs publicly without visible
    provenance and disclaimers.
    """
    
    @staticmethod
    def determine_level(
        mode: CurriculumMode,
        institution_type: InstitutionType | None = None,
    ) -> DisclaimerLevel:
        """Determine required disclaimer level."""
        if mode == CurriculumMode.K12:
            return DisclaimerLevel.NONE
        
        # University/syllabus mode
        if institution_type == InstitutionType.ACCREDITED:
            return DisclaimerLevel.STANDARD
        elif institution_type == InstitutionType.UNKNOWN:
            return DisclaimerLevel.ENHANCED
        else:  # TRAINING_PROVIDER
            return DisclaimerLevel.MAXIMUM
    
    @staticmethod
    def generate(
        mode: CurriculumMode,
        institution_type: InstitutionType | None = None,
        custom_disclaimer: str | None = None,
    ) -> str | None:
        """
        Generate appropriate disclaimer.
        
        Args:
            mode: K12 or SYLLABUS
            institution_type: Type of institution (for SYLLABUS mode)
            custom_disclaimer: Override with custom text
            
        Returns:
            Disclaimer text or None for K-12
        """
        if custom_disclaimer:
            return custom_disclaimer
        
        level = DisclaimerGenerator.determine_level(mode, institution_type)
        return DISCLAIMER_TEMPLATES[level]


# =============================================================================
# PROVENANCE METADATA
# =============================================================================

class ProvenanceMetadata(BaseModel):
    """
    Provenance metadata for university curriculum outputs.
    
    Required for all university outputs to maintain transparency
    about source, extraction date, and confidence.
    """
    source_url: NonEmptyStr = Field(
        description="URL where the syllabus was obtained"
    )
    source_domain: str = Field(
        description="Domain of the source (e.g., 'mit.edu')"
    )
    extraction_date: date = Field(
        default_factory=date.today,
        description="Date when content was extracted"
    )
    extraction_confidence: ConfidenceScore = Field(
        description="Confidence score of extraction (0.0-1.0)"
    )
    curriculum_mode: CurriculumMode = Field(
        description="K12 or SYLLABUS"
    )
    institution_name: str | None = Field(
        default=None,
        description="Name of institution"
    )
    institution_type: InstitutionType = Field(
        default=InstitutionType.UNKNOWN,
        description="Accreditation status"
    )
    course_code: str | None = Field(
        default=None,
        description="Course code if available"
    )
    semester: str | None = Field(
        default=None,
        description="Semester/term if specified"
    )
    last_verified: date | None = Field(
        default=None,
        description="Date of last verification"
    )
    
    @property
    def age_days(self) -> int:
        """Days since extraction."""
        return (date.today() - self.extraction_date).days
    
    @property
    def is_stale(self) -> bool:
        """Check if content is stale (>90 days since extraction)."""
        return self.age_days > 90
    
    @property
    def staleness_level(self) -> str:
        """Get staleness level for UI indicators."""
        if self.age_days <= 30:
            return "fresh"
        elif self.age_days <= 60:
            return "aging"
        elif self.age_days <= 120:
            return "stale"
        else:
            return "expired"
    
    def format_provenance(self) -> str:
        """Format provenance for display."""
        parts = []
        
        if self.institution_name:
            parts.append(f"Institution: {self.institution_name}")
        if self.course_code:
            parts.append(f"Course: {self.course_code}")
        if self.semester:
            parts.append(f"Term: {self.semester}")
        
        parts.append(f"Source: {self.source_url}")
        parts.append(f"Extracted: {self.extraction_date.isoformat()}")
        parts.append(f"Confidence: {self.extraction_confidence:.0%}")
        
        return " | ".join(parts)


# =============================================================================
# GOVERNANCE DECISION UTILITIES
# =============================================================================

class GovernanceDecision(BaseModel):
    """
    Governance decision for a curriculum output.
    
    Encapsulates all governance-related decisions:
    - Whether to allow output
    - Required disclaimers
    - Confidence adjustments
    - Staleness warnings
    """
    allow_output: bool = Field(description="Whether output is permitted")
    disclaimer_level: DisclaimerLevel = Field(description="Required disclaimer level")
    disclaimer_text: str | None = Field(description="Disclaimer to display")
    requires_provenance: bool = Field(description="Whether provenance must be shown")
    staleness_warning: str | None = Field(description="Staleness warning if applicable")
    confidence_adjustment: float = Field(
        default=0.0,
        description="Adjustment to confidence score (e.g., -0.05 for staleness)"
    )
    blocks_production: bool = Field(
        default=False,
        description="Whether this blocks production deployment"
    )


def evaluate_governance(
    mode: CurriculumMode,
    provenance: ProvenanceMetadata | None = None,
    institution_type: InstitutionType | None = None,
) -> GovernanceDecision:
    """
    Evaluate governance requirements for a curriculum output.
    
    Args:
        mode: K12 or SYLLABUS
        provenance: Provenance metadata if available
        institution_type: Type of institution
        
    Returns:
        GovernanceDecision with all requirements
    """
    # K-12 is straightforward
    if mode == CurriculumMode.K12:
        return GovernanceDecision(
            allow_output=True,
            disclaimer_level=DisclaimerLevel.NONE,
            disclaimer_text=None,
            requires_provenance=False,
            staleness_warning=None,
        )
    
    # University/syllabus mode requires more checks
    inst_type = institution_type or InstitutionType.UNKNOWN
    
    disclaimer_level = DisclaimerGenerator.determine_level(mode, inst_type)
    disclaimer_text = DisclaimerGenerator.generate(mode, inst_type)
    
    # Calculate staleness warning
    staleness_warning = None
    confidence_adjustment = 0.0
    
    if provenance:
        if provenance.staleness_level == "stale":
            staleness_warning = (
                f"⚠️ Content is {provenance.age_days} days old. "
                "Syllabus may have changed."
            )
            confidence_adjustment = -0.05
        elif provenance.staleness_level == "expired":
            staleness_warning = (
                f"⚠️ Content is {provenance.age_days} days old and likely outdated. "
                "Re-verification recommended."
            )
            confidence_adjustment = -0.10
    
    return GovernanceDecision(
        allow_output=True,  # Provisionally enabled
        disclaimer_level=disclaimer_level,
        disclaimer_text=disclaimer_text,
        requires_provenance=True,  # Always required for university
        staleness_warning=staleness_warning,
        confidence_adjustment=confidence_adjustment,
        blocks_production=inst_type == InstitutionType.TRAINING_PROVIDER,
    )
