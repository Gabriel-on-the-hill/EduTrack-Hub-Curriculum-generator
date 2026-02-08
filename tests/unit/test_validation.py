"""
Unit tests for validation middleware.

Tests verify:
1. Schema validation works correctly
2. Confidence thresholds are enforced
3. Grounding gates reject insufficient coverage
4. Fallback tiers are determined correctly
"""

from uuid import uuid4

import pytest

from src.utils.validation import (
    validate_schema,
    check_confidence_threshold,
    enforce_grounding_gate,
    determine_fallback_tier,
    SchemaValidationError,
    ConfidenceThresholdError,
    GroundingError,
    AgentOutputValidator,
)
from src.schemas.request import NormalizedRequest, NormalizedFields
from src.schemas.base import FallbackTier, ConfidenceThresholds


# =============================================================================
# SCHEMA VALIDATION TESTS
# =============================================================================

class TestValidateSchema:
    """Tests for validate_schema function."""

    def test_valid_data_returns_model(self) -> None:
        """Valid data should return a validated model instance."""
        data = {
            "request_id": str(uuid4()),
            "raw_prompt": "Grade 9 Biology for Nigeria",
            "normalized": {
                "country": "Nigeria",
                "country_code": "NG",
                "grade": "Grade 9",
                "subject": "Biology",
            },
            "confidence": 0.95,
        }
        result = validate_schema(NormalizedRequest, data)
        assert isinstance(result, NormalizedRequest)
        assert result.confidence == 0.95

    def test_invalid_data_raises_error(self) -> None:
        """Invalid data should raise SchemaValidationError."""
        data = {
            "request_id": str(uuid4()),
            "raw_prompt": "test",
            "normalized": {
                "country": "Nigeria",
                "country_code": "INVALID",  # Not ISO-2
                "grade": "Grade 9",
                "subject": "Biology",
            },
            "confidence": 0.95,
        }
        with pytest.raises(SchemaValidationError) as exc_info:
            validate_schema(NormalizedRequest, data)
        assert exc_info.value.schema_name == "NormalizedRequest"


# =============================================================================
# CONFIDENCE THRESHOLD TESTS
# =============================================================================

class TestCheckConfidenceThreshold:
    """Tests for check_confidence_threshold function."""

    def test_above_threshold_passes(self) -> None:
        """Confidence above threshold should pass without error."""
        # Should not raise
        check_confidence_threshold(0.9, "intent_classification")

    def test_below_threshold_raises_error(self) -> None:
        """Confidence below threshold should raise ConfidenceThresholdError."""
        with pytest.raises(ConfidenceThresholdError) as exc_info:
            check_confidence_threshold(0.8, "intent_classification")  # Requires 0.85
        assert exc_info.value.actual == 0.8
        assert exc_info.value.required == ConfidenceThresholds.INTENT_CLASSIFICATION

    def test_custom_threshold(self) -> None:
        """Custom threshold should be used when provided."""
        # Should pass with custom threshold
        check_confidence_threshold(0.7, "custom_stage", threshold=0.6)
        
        # Should fail with custom threshold
        with pytest.raises(ConfidenceThresholdError):
            check_confidence_threshold(0.5, "custom_stage", threshold=0.6)


# =============================================================================
# GROUNDING GATE TESTS
# =============================================================================

class TestEnforceGroundingGate:
    """Tests for enforce_grounding_gate function."""

    def test_sufficient_coverage_passes(self) -> None:
        """Coverage >= 0.8 should pass."""
        # Should not raise
        enforce_grounding_gate(0.8)
        enforce_grounding_gate(0.95)
        enforce_grounding_gate(1.0)

    def test_insufficient_coverage_raises_error(self) -> None:
        """Coverage < 0.8 should raise GroundingError."""
        with pytest.raises(GroundingError) as exc_info:
            enforce_grounding_gate(0.79)
        assert exc_info.value.coverage == 0.79


# =============================================================================
# FALLBACK TIER TESTS
# =============================================================================

class TestDetermineFallbackTier:
    """Tests for determine_fallback_tier function."""

    def test_high_confidence_no_failures_tier_0(self) -> None:
        """High confidence with no failures should return Tier 0."""
        result = determine_fallback_tier(0.9, failure_count=0)
        assert result == FallbackTier.TIER_0

    def test_low_confidence_tier_1(self) -> None:
        """Low confidence should trigger Tier 1 escalation."""
        result = determine_fallback_tier(0.65, failure_count=0)
        assert result == FallbackTier.TIER_1

    def test_one_failure_tier_1(self) -> None:
        """One failure should trigger Tier 1 escalation."""
        result = determine_fallback_tier(0.9, failure_count=1)
        assert result == FallbackTier.TIER_1

    def test_two_failures_tier_2(self) -> None:
        """Two or more failures should trigger Tier 2 safe mode."""
        result = determine_fallback_tier(0.9, failure_count=2)
        assert result == FallbackTier.TIER_2
        
        result = determine_fallback_tier(0.9, failure_count=5)
        assert result == FallbackTier.TIER_2


# =============================================================================
# AGENT OUTPUT VALIDATOR TESTS
# =============================================================================

class TestAgentOutputValidator:
    """Tests for AgentOutputValidator context manager."""

    def test_valid_output_validation(self) -> None:
        """Valid output should be validated successfully."""
        data = {
            "request_id": str(uuid4()),
            "raw_prompt": "Grade 9 Biology for Nigeria",
            "normalized": {
                "country": "Nigeria",
                "country_code": "NG",
                "grade": "Grade 9",
                "subject": "Biology",
            },
            "confidence": 0.95,
        }
        
        with AgentOutputValidator("TestAgent", NormalizedRequest) as validator:
            result = validator.validate(data)
        
        assert isinstance(result, NormalizedRequest)

    def test_invalid_output_raises_error(self) -> None:
        """Invalid output should raise error within context."""
        data = {"invalid": "data"}
        
        with pytest.raises(SchemaValidationError):
            with AgentOutputValidator("TestAgent", NormalizedRequest) as validator:
                validator.validate(data)
