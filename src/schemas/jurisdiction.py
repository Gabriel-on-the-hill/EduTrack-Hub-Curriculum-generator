"""
Jurisdiction Resolution Schema (Blueprint Section 13.2)

This schema defines the output of the Decision Engine for jurisdiction resolution.
It determines which jurisdiction's curriculum to use based on the JAS score.

Validation rules (from Blueprint):
- jas_score > 0.7 AND assumption_type = assumed → INVALID
- confidence < 0.6 → must ask user
"""

from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from src.schemas.base import (
    AssumptionType,
    ConfidenceScore,
    JurisdictionLevel,
    NonEmptyStr,
)


class JurisdictionInfo(BaseModel):
    """Details about the resolved jurisdiction."""
    level: JurisdictionLevel = Field(
        description="Level: national, state, or county"
    )
    name: str | None = Field(
        default=None,
        description="Name of the specific jurisdiction (null for national)"
    )
    parent: UUID | None = Field(
        default=None,
        description="UUID of parent jurisdiction (null for national)"
    )


class JurisdictionResolution(BaseModel):
    """
    Output of Jurisdiction Resolution (Decision Engine).
    
    Blueprint Section 13.2:
    - jas_score > 0.7 AND assumption_type = assumed → INVALID
    - confidence < 0.6 → must ask user
    """
    request_id: UUID = Field(
        description="Links back to the original request"
    )
    jurisdiction: JurisdictionInfo = Field(
        description="The resolved jurisdiction details"
    )
    jas_score: ConfidenceScore = Field(
        description="Jurisdiction Ambiguity Score (0.0-1.0)"
    )
    assumption_type: AssumptionType = Field(
        description="How the jurisdiction was determined"
    )
    confidence: ConfidenceScore = Field(
        description="Overall confidence in the resolution"
    )

    @model_validator(mode="after")
    def validate_assumption_rules(self) -> "JurisdictionResolution":
        """
        Enforce Blueprint rules:
        - jas_score > 0.7 AND assumption_type = assumed → INVALID
        - confidence < 0.6 → must ask user (we raise an error to halt)
        """
        # Rule 1: High ambiguity cannot be assumed
        if self.jas_score > 0.7 and self.assumption_type == AssumptionType.ASSUMED:
            raise ValueError(
                f"JAS score {self.jas_score} > 0.7 with assumption_type='assumed' "
                f"is INVALID. High ambiguity requires explicit user confirmation."
            )
        
        # Rule 2: Low confidence requires user interaction
        if self.confidence < 0.6:
            raise ValueError(
                f"Jurisdiction confidence {self.confidence} < 0.6 - "
                f"must ask user for clarification before proceeding."
            )
        
        return self

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "request_id": "123e4567-e89b-12d3-a456-426614174000",
                    "jurisdiction": {
                        "level": "national",
                        "name": None,
                        "parent": None
                    },
                    "jas_score": 0.3,
                    "assumption_type": "assumed",
                    "confidence": 0.85
                }
            ]
        }
    }
