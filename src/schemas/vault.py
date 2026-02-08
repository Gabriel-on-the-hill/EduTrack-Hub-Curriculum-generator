"""
Vault Lookup Schema (Blueprint Section 13.3)

This schema defines the output of the Vault Lookup (Controller).
It determines if a curriculum exists in the cache and at what confidence level.

Rules (from Blueprint):
- If found = false → enqueue cold-start job
- If found = true AND confidence >= 0.8 → serve immediately
- If found = true AND confidence < 0.8 → warn user + offer refresh
"""

from uuid import UUID

from pydantic import BaseModel, Field

from src.schemas.base import ConfidenceScore, VaultSource


class VaultLookupResult(BaseModel):
    """
    Output of Vault Lookup (Controller).
    
    Blueprint Section 13.3:
    - found = false → enqueue cold-start job
    - found = true AND confidence >= 0.8 → serve immediately
    - found = true AND confidence < 0.8 → warn user + offer refresh
    """
    request_id: UUID = Field(
        description="Links back to the original request"
    )
    found: bool = Field(
        description="Whether a matching curriculum was found in the vault"
    )
    curriculum_id: UUID | None = Field(
        default=None,
        description="UUID of the found curriculum (null if not found)"
    )
    confidence: ConfidenceScore | None = Field(
        default=None,
        description="Confidence score of the match (null if not found)"
    )
    source: VaultSource | None = Field(
        default=None,
        description="Where the curriculum was found: cache, parent, or national"
    )

    def should_serve_immediately(self) -> bool:
        """Check if curriculum can be served without refresh warning."""
        return self.found and self.confidence is not None and self.confidence >= 0.8

    def should_warn_and_offer_refresh(self) -> bool:
        """Check if curriculum exists but needs refresh warning."""
        return self.found and self.confidence is not None and self.confidence < 0.8

    def should_enqueue_cold_start(self) -> bool:
        """Check if we need to fetch curriculum from scratch."""
        return not self.found

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "request_id": "123e4567-e89b-12d3-a456-426614174000",
                    "found": True,
                    "curriculum_id": "987e6543-e21b-12d3-a456-426614174000",
                    "confidence": 0.92,
                    "source": "cache"
                },
                {
                    "request_id": "123e4567-e89b-12d3-a456-426614174000",
                    "found": False,
                    "curriculum_id": None,
                    "confidence": None,
                    "source": None
                }
            ]
        }
    }
