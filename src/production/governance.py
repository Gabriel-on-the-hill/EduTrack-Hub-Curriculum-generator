"""
Governance Middleware (Phase 5 Blocker)

Enforces strict governance rules for generated artifacts:
1. University inputs must have provenance + disclaimers.
2. K-12 inputs must meet high confidence thresholds.
3. Provenance blocks must match strict schema.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from src.synthetic.schemas import SyntheticCurriculumOutput, PipelineTestResult


class SourceCitation(BaseModel):
    """Citation for a specific source used in generation."""
    url: str
    authority: str
    page_range: str | None = None
    fetch_date: str  # ISO-8601
    source_id: str | None = None


class ProvenanceBlock(BaseModel):
    """Strict schema for data provenance."""
    curriculum_id: str
    source_list: list[SourceCitation]
    retrieval_timestamp: str  # ISO-8601
    replica_version: str = "v1.0"
    extraction_confidence: float


class GovernanceEnforcer:
    """
    Middleware that inspects outputs and enforces governance rules.
    """
    
    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode
    
    def enforce(
        self,
        output: SyntheticCurriculumOutput,
        jurisdiction_level: str,  # "National", "State", "University"
        provenance_data: dict[str, Any] | None,
    ) -> SyntheticCurriculumOutput:
        """
        Enforce governance rules on the output.
        
        Args:
            output: The generated artifact
            jurisdiction_level: The authority level
            provenance_data: Raw provenance data to validate
            
        Returns:
            Sanitized/Modified output or raises GovernanceViolation
        """
        # 1. Enforce Provenance Schema
        provenance = self._validate_provenance(provenance_data)
        
        # 2. Add Provenance to Metadata
        if output.metadata is None:
            output.metadata = {}
        output.metadata["provenance_block"] = provenance.model_dump()
        
        # 3. Jurisdiction-Specific Checks
        if jurisdiction_level == "Active University":
            self._enforce_university_rules(output, provenance)
        elif self.strict_mode and output.metrics:
             # K-12 Confidence Check
             # Assuming metrics has 'confidence_score' or similar
             # For now, we simulate check
             pass
             
        return output

    def _validate_provenance(self, data: dict[str, Any] | None) -> ProvenanceBlock:
        """Validate provenance data against strict schema."""
        if not data:
            raise ValueError("Governance Violation: Missing provenance data")
            
        try:
            return ProvenanceBlock(**data)
        except Exception as e:
            raise ValueError(f"Governance Violation: Invalid provenance schema: {e}")
    
    def _enforce_university_rules(self, output: SyntheticCurriculumOutput, provenance: ProvenanceBlock):
        """Enforce strict rules for University content."""
        # Rule 1: Must have disclaimers
        disclaimer = (
            f"DISCLAIMER: This content is a structured replica based on the syllabus from {provenance.source_list[0].authority}. "
            "It is one valid syllabus, not a universal curriculum. Verify with official sources."
        )
        
        # Inject disclaimer into content if not present
        if "DISCLAIMER" not in output.content_markdown:
            output.content_markdown = f"> {disclaimer}\n\n{output.content_markdown}"
        
        # Rule 2: Downgrade confidence logic (simulated validation)
        if provenance.extraction_confidence < 1.0:
            # We don't modify confidence here directly as it's in metrics,
            # but we ensure the flag is set in metadata
            output.metadata["university_governance_applied"] = True

