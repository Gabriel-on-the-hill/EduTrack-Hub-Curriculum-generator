"""
Base types and constants used across all schemas.

This module defines shared enums, types, and configuration
that ensure consistency across the entire system.
"""

from enum import Enum
from typing import Annotated
from uuid import UUID

from pydantic import Field


# =============================================================================
# CONFIDENCE THRESHOLDS (Section 23 of Blueprint)
# =============================================================================

class ConfidenceThresholds:
    """
    Global confidence thresholds as defined in Section 23.
    
    Anything below threshold → pause, retry, or ask user.
    """
    INTENT_CLASSIFICATION: float = 0.85
    JURISDICTION_RESOLUTION: float = 0.80
    SOURCE_VALIDATION: float = 0.90
    OCR_PARSING: float = 0.70
    GENERATION_GROUNDING: float = 1.0  # Binary - must be exact


# =============================================================================
# ENUMS
# =============================================================================

class JurisdictionLevel(str, Enum):
    """Level of jurisdiction for a curriculum."""
    NATIONAL = "national"
    STATE = "state"
    COUNTY = "county"
    # Higher education levels
    UNIVERSITY = "university"  # University-wide requirements
    DEPARTMENT = "department"  # Department/faculty-specific


class AssumptionType(str, Enum):
    """How the jurisdiction was determined."""
    ASSUMED = "assumed"
    USER_CONFIRMED = "user_confirmed"
    EXPLICIT = "explicit"


class CurriculumStatus(str, Enum):
    """Status of a curriculum in the vault."""
    ACTIVE = "active"
    STALE = "stale"
    CONFLICTED = "conflicted"


class CurriculumMode(str, Enum):
    """
    Semantic contract for curriculum sources.
    
    K-12 = Canonical curriculum from government authority
    SYLLABUS = Institution-specific syllabus reference
    """
    K12 = "k12"  # Government-mandated, single source of truth
    SYLLABUS = "syllabus"  # Institution-specific, no universality claims


class InstitutionType(str, Enum):
    """
    Trust tier for educational institutions.
    
    Used for university/college sources to indicate verification level.
    """
    ACCREDITED = "accredited"  # Verified accredited institution
    UNKNOWN = "unknown"  # Cannot verify accreditation status
    TRAINING_PROVIDER = "training_provider"  # Non-degree training org


class LicenseType(str, Enum):
    """License status of a source document."""
    PERMISSIVE = "permissive"
    UNCLEAR = "unclear"
    RESTRICTED = "restricted"
    # Extended types for detailed classification
    GOVERNMENT = "government"  # Government/official publications
    PUBLIC_DOMAIN = "public_domain"  # Public domain works
    CREATIVE_COMMONS = "creative_commons"  # CC licensed works
    EDUCATIONAL = "educational"  # Educational use license
    UNKNOWN = "unknown"  # Cannot determine license


class AgentStatus(str, Enum):
    """Status of an agent operation."""
    SUCCESS = "success"
    FAILED = "failed"
    LOW_CONFIDENCE = "low_confidence"
    APPROVED = "approved"
    CONFLICTED = "conflicted"
    REJECTED = "rejected"


class AuthorityHint(str, Enum):
    """Hint about the authority of a source."""
    OFFICIAL = "official"
    UNKNOWN = "unknown"


class VaultSource(str, Enum):
    """Source of a vault lookup result."""
    CACHE = "cache"
    PARENT = "parent"
    NATIONAL = "national"


class GenerationRequestType(str, Enum):
    """Type of generation request."""
    LESSON_PLAN = "lesson_plan"
    QUIZ = "quiz"
    SUMMARY = "summary"


class FallbackTier(str, Enum):
    """Model fallback tier for cost-aware routing."""
    TIER_0 = "tier_0"  # Cost-optimized path
    TIER_1 = "tier_1"  # Accuracy escalation
    TIER_2 = "tier_2"  # Deterministic safe mode


# =============================================================================
# ANNOTATED TYPES
# =============================================================================

# Confidence score must be between 0.0 and 1.0
ConfidenceScore = Annotated[float, Field(ge=0.0, le=1.0)]

# Non-empty string
NonEmptyStr = Annotated[str, Field(min_length=1)]

# ISO-2 country code (2 uppercase letters)
CountryCode = Annotated[str, Field(pattern=r"^[A-Z]{2}$")]

# Page range string (e.g., "10-15" or "10")
PageRange = Annotated[str, Field(pattern=r"^\d+(-\d+)?$")]
