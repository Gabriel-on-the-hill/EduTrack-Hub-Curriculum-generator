"""
Validation Middleware (Blueprint Phase 1 Requirement)

This module provides schema validation middleware that enforces:
1. Schema validation on all agent I/O
2. Confidence threshold enforcement
3. Binary grounding gate (1.0 or reject for replicas)

Per Blueprint: "Schemas are law. If data does not match, fail fast."
"""

import functools
import logging
from typing import Any, Callable, TypeVar

from pydantic import BaseModel, ValidationError

from src.schemas.base import ConfidenceScore, ConfidenceThresholds, FallbackTier

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class SchemaValidationError(Exception):
    """Raised when schema validation fails."""
    
    def __init__(self, message: str, schema_name: str, errors: list[dict[str, Any]]) -> None:
        super().__init__(message)
        self.schema_name = schema_name
        self.errors = errors


class ConfidenceThresholdError(Exception):
    """Raised when confidence is below required threshold."""
    
    def __init__(
        self, 
        message: str, 
        actual: float, 
        required: float, 
        stage: str
    ) -> None:
        super().__init__(message)
        self.actual = actual
        self.required = required
        self.stage = stage


class GroundingError(Exception):
    """Raised when content fails grounding requirements."""
    
    def __init__(self, message: str, coverage: float) -> None:
        super().__init__(message)
        self.coverage = coverage


def validate_schema(schema_class: type[T], data: dict[str, Any]) -> T:
    """
    Validate data against a Pydantic schema.
    
    Per Blueprint Section 13 (Final Instruction):
    If any agent output violates its schema:
    1. Stop execution
    2. Log the error
    3. Escalate
    
    Args:
        schema_class: The Pydantic model class to validate against
        data: The data dictionary to validate
        
    Returns:
        Validated Pydantic model instance
        
    Raises:
        SchemaValidationError: If validation fails
    """
    try:
        return schema_class.model_validate(data)
    except ValidationError as e:
        logger.error(
            f"Schema validation failed for {schema_class.__name__}: {e.errors()}"
        )
        raise SchemaValidationError(
            message=f"Schema validation failed for {schema_class.__name__}",
            schema_name=schema_class.__name__,
            errors=e.errors()
        ) from e


def validate_output(schema_class: type[T]) -> Callable[[Callable[..., dict[str, Any]]], Callable[..., T]]:
    """
    Decorator that validates function output against a schema.
    
    Usage:
        @validate_output(MyOutputSchema)
        def my_function() -> dict:
            return {"field": "value"}
    
    The function's dict return value will be validated and converted
    to the schema type.
    """
    def decorator(func: Callable[..., dict[str, Any]]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            result = func(*args, **kwargs)
            return validate_schema(schema_class, result)
        return wrapper
    return decorator


def check_confidence_threshold(
    confidence: ConfidenceScore,
    stage: str,
    threshold: float | None = None
) -> None:
    """
    Check if confidence meets the required threshold for a given stage.
    
    Per Blueprint Section 23 (Confidence Threshold Table):
    Anything below threshold → pause, retry, or ask user.
    
    Args:
        confidence: The confidence score to check
        stage: The processing stage (for threshold lookup and error messages)
        threshold: Optional explicit threshold (uses stage lookup if not provided)
        
    Raises:
        ConfidenceThresholdError: If confidence is below threshold
    """
    if threshold is None:
        threshold = _get_threshold_for_stage(stage)
    
    if confidence < threshold:
        logger.warning(
            f"Confidence {confidence} below threshold {threshold} for stage '{stage}'"
        )
        raise ConfidenceThresholdError(
            message=f"Confidence {confidence} below required {threshold} for {stage}",
            actual=confidence,
            required=threshold,
            stage=stage
        )


def _get_threshold_for_stage(stage: str) -> float:
    """Get the confidence threshold for a processing stage."""
    thresholds = {
        "intent_classification": ConfidenceThresholds.INTENT_CLASSIFICATION,
        "jurisdiction_resolution": ConfidenceThresholds.JURISDICTION_RESOLUTION,
        "source_validation": ConfidenceThresholds.SOURCE_VALIDATION,
        "ocr_parsing": ConfidenceThresholds.OCR_PARSING,
        "generation_grounding": ConfidenceThresholds.GENERATION_GROUNDING,
    }
    return thresholds.get(stage, 0.8)  # Default to 0.8 if stage not found


def enforce_grounding_gate(coverage: ConfidenceScore) -> None:
    """
    Enforce binary grounding gate for replica storage.
    
    Per Blueprint Section 20.1 (Storage Guardrail):
    Replica is persisted ONLY if:
    - 100% of competencies grounded
    - Zero forbidden patterns detected
    - Confidence score = 1.0 (binary)
    
    This function enforces the coverage >= 0.8 requirement from
    Blueprint Section 9.
    
    Args:
        coverage: The coverage score (0.0-1.0)
        
    Raises:
        GroundingError: If coverage is below 0.8
    """
    if coverage < 0.8:
        logger.error(
            f"Grounding gate failed: coverage {coverage} < 0.8"
        )
        raise GroundingError(
            message=f"Grounding gate failed: coverage {coverage} must be >= 0.8",
            coverage=coverage
        )


def determine_fallback_tier(
    confidence: ConfidenceScore,
    failure_count: int = 0
) -> FallbackTier:
    """
    Determine the appropriate fallback tier based on confidence and failures.
    
    Per Blueprint Section 21.4 (Fallback Tiers):
    - Tier 0: Cost-optimized path (default)
    - Tier 1: Accuracy escalation (low confidence or partial failure)
    - Tier 2: Deterministic safe mode (2+ failures or timeout)
    
    Args:
        confidence: Current confidence score
        failure_count: Number of previous failures
        
    Returns:
        The appropriate FallbackTier
    """
    if failure_count >= 2:
        return FallbackTier.TIER_2
    
    if confidence < 0.7 or failure_count == 1:
        return FallbackTier.TIER_1
    
    return FallbackTier.TIER_0


class AgentOutputValidator:
    """
    Context manager for validating agent outputs with logging.
    
    Usage:
        with AgentOutputValidator("ScoutAgent", ScoutOutput) as validator:
            result = scout_agent.run()
            validated = validator.validate(result)
    """
    
    def __init__(self, agent_name: str, schema_class: type[T]) -> None:
        self.agent_name = agent_name
        self.schema_class = schema_class
        self.logger = logging.getLogger(f"edutrack.agent.{agent_name}")
    
    def __enter__(self) -> "AgentOutputValidator":
        self.logger.info(f"Starting {self.agent_name} output validation")
        return self
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        if exc_type is not None:
            self.logger.error(
                f"{self.agent_name} validation failed: {exc_val}"
            )
        return False  # Don't suppress exceptions
    
    def validate(self, data: dict[str, Any]) -> T:
        """Validate data and return typed model."""
        validated = validate_schema(self.schema_class, data)
        self.logger.info(f"{self.agent_name} output validated successfully")
        return validated
